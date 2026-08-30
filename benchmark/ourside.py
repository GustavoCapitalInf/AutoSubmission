"""Our-side pipeline runs - strictly offline.

Source text is resolved exactly the way the corpus gate does:
``balance_forensic_audit.source_markdown(path, ocr_cache=tests/corpus_cache)``
(native text first; image-only PDFs served from the committed OCR artifacts;
no live OCR, no Gemini, no network).  Analysis uses
``analysis.pipeline.analyze_document(..., parse_mode="deterministic")`` and the
production ``document_report_to_dict`` contract.  Package aggregation reuses the same
code path the webapp serves (``webapp.app._package_analysis``) with in-memory
jobs, so package semantics match production.  None of those modules are
modified by this package.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from balance_forensic_audit import source_markdown
from analysis.payload_shape import refuse_document_payload
from analysis.pipeline import analyze_document
from analysis.serialization import document_report_to_dict
from webapp.jobs import Job
from webapp.app import _package_analysis

from .manifest import BenchmarkSet


@dataclass
class OurFileResult:
    """Production analysis payload for one statement PDF."""

    relative_path: str
    source_type: str            # digital/native | scanned/local_ocr
    markdown: str
    payload: dict[str, Any]

    def _account(self) -> dict[str, Any]:
        """This file's ONE account payload, or a refusal.

        The benchmark compares our published figures against `expectations`,
        which declares ONE opening, ONE ending and ONE ADB per statement
        FILENAME and has no account column. So a document publishing several
        accounts has nowhere here to be compared, and every view below refuses
        rather than answering about one of them — measured before this
        teaching, all three returned EMPTY dicts, which the comparison would
        have read as "our side produced nothing" for a document that produced
        everything. Admitting a second account is a truth-set ceremony on the
        two audit CSVs, not a shim here.
        """
        refuse_document_payload(
            self.payload, surface="benchmark/ourside.py::OurFileResult")
        return self.payload

    @property
    def statement(self) -> dict[str, Any]:
        return self._account().get("statement") or {}

    @property
    def metrics(self) -> dict[str, Any]:
        return self._account().get("metrics") or {}

    @property
    def reconciliation(self) -> dict[str, Any]:
        return self._account().get("reconciliation") or {}

    @property
    def detection(self) -> dict[str, Any]:
        return self._account().get("detection") or {}

    def daily_ledger(self) -> dict[str, float]:
        """Validated per-day ledger (ISO date -> EOD balance); empty if withheld."""
        adb = self.metrics.get("adb") or {}
        if not adb.get("ok"):
            return {}
        return {
            str(day.get("date")): day.get("ending_balance")
            for day in adb.get("daily_balances") or []
            if day.get("date") is not None and day.get("ending_balance") is not None
        }

    def ledger_rows_matching(self, tokens: tuple[str, ...]) -> list[dict[str, Any]]:
        """Transactions whose description contains any token (case-insensitive)."""
        rows = []
        lowered = tuple(token.lower() for token in tokens)
        for txn in self.statement.get("transactions") or []:
            description = (txn.get("description") or "").lower()
            if any(token in description for token in lowered):
                rows.append(txn)
        return rows


@dataclass
class OurSetResult:
    """Our pipeline output for one benchmark set (files + optional package)."""

    set_name: str
    files: list[OurFileResult] = field(default_factory=list)
    package: dict[str, Any] | None = None

    @property
    def primary(self) -> OurFileResult:
        return self.files[0]


def run_set(
    benchmark_set: BenchmarkSet,
    corpus_root: Path,
    ocr_cache: Path,
) -> OurSetResult:
    """Analyze every PDF of a set offline; aggregate packages like production."""
    result = OurSetResult(set_name=benchmark_set.name)
    jobs: list[Job] = []
    for relative in benchmark_set.files:
        path = corpus_root / relative
        markdown, source_type, _pdf_bytes = source_markdown(path, ocr_cache=ocr_cache)
        payload = document_report_to_dict(
            analyze_document(markdown, parse_mode="deterministic"))
        result.files.append(
            OurFileResult(
                relative_path=relative,
                source_type=source_type,
                markdown=markdown,
                payload=payload,
            )
        )
        jobs.append(
            Job(id=f"bench-{len(jobs)}", filename=path.name, status="done", analysis=payload)
        )
    if benchmark_set.package:
        result.package = _package_analysis(jobs)
    return result
