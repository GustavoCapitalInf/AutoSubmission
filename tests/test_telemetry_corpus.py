"""Telemetry against the pinned 109: the outcome anchor and the sensitivity proof.

`test_telemetry_reproduces_the_gate_outcome_split` carries the `corpus` marker
(it re-analyses all 109 statements, minutes) and is deselected from the default
run — `pytest -m corpus`, alongside the gate itself.

The sensitivity test runs by default over a small sample: it is the invariant
that makes always-on telemetry safe, so it must not be something a developer
only sees on a corpus run.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import corpus_gate
from analysis.pipeline import analyze_markdown
from analysis.serialization import report_to_dict
from corpus_artifacts import cached_markdown
from ocr.inspect import inspect_pdf
from telemetry import (
    DispatchCollector,
    StageTimer,
    build_record,
    dispatch_section,
    document_section,
    model_calls_for,
    score_vector,
    source_section,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "Bank Statements"
CACHE = ROOT / "tests" / "corpus_cache"

#: The three proven source contradictions the gate withholds. Same set as
#: corpus_gate.WITHHELD_STATEMENTS, reached by a completely different route.
WITHHELD = {
    "Ace_Auto_Final_Cut.pdf",
    "BMO_Statement_January_2026 Final-1-2 (1).pdf",
    "IBC April (1).pdf",
}


def _manifest() -> list[str]:
    return corpus_gate.manifest_paths(corpus_gate.read_csv(corpus_gate.BALANCE_CSV))


def _telemetry_for(rel: str) -> tuple[dict, dict | None]:
    """One record for one pinned statement, resolved offline exactly as the gate does.

    The production intake ladder with both OCR rungs disabled: native only,
    layout-aware (Navy Federal / TD Canada / Wells / Desjardins readers come
    before the generic one, and using the generic reader alone silently
    produces different markdown for those four banks). Image-only statements
    fall through to their committed OCR artifact, which is what keeps this
    offline and deterministic.
    """
    from ocr.pipeline import parse_statement

    raw = (CORPUS / rel).read_bytes()
    profile = inspect_pdf(raw)
    timer, collector = StageTimer(), DispatchCollector()
    with timer.time("read"):
        doc = parse_statement(
            raw,
            source_file=Path(rel).name,
            profile=profile,
            force_ocr=False,
            allow_local_ocr=False,
            allow_visual_ocr=False,
        )
        markdown = doc.to_markdown() if doc is not None else cached_markdown(raw, CACHE)
    payload, error_type, escalated = None, None, False
    try:
        with timer.time("analysis", "miss"):
            report = analyze_markdown(
                markdown, parse_mode="deterministic", on_dispatch=collector
            )
        payload = report_to_dict(report)
        escalated = report.escalated
    except Exception as exc:
        error_type = type(exc).__name__
    scores, registration_count = score_vector(markdown)
    record = build_record(
        run_id="corpus-anchor",
        emitter="batch",
        document=document_section(profile.content_sha256, len(raw), profile),
        source=source_section(doc),
        dispatch=dispatch_section(
            collector.dispatch, scores, registration_count,
            source="live" if collector.seen else "unavailable",
        ),
        stages=timer.as_dict(),
        model_calls=model_calls_for(doc, payload),
        payload=payload,
        escalated=escalated,
        error_type=error_type,
    )
    return record, payload


@pytest.mark.corpus
def test_telemetry_reproduces_the_gate_outcome_split():
    """The 106/3 anchor, from an independent code path.

    The corpus gate proves 106 PASS / 3 WITHHELD by re-running two forensic
    oracles. Telemetry reaches the same withheld set by reading the product's
    own serialized payload — no oracle, no audit CSV. `validated` and `review`
    are a FINER partition of the gate's PASS (approval is a different question
    from "the audited values reproduce"), so the invariant is: the 3 withheld
    are exactly the gate's 3, nothing failed, and the remaining 106 are
    validated-or-review.
    """
    manifest = _manifest()
    assert len(manifest) == corpus_gate.EXPECTED_PDF_COUNT

    records = [_telemetry_for(rel)[0] for rel in manifest]
    classes = [record["outcome"]["class"] for record in records]

    withheld = {
        Path(rel).name
        for rel, record in zip(manifest, records)
        if record["outcome"]["class"] == "withheld"
    }
    assert withheld == WITHHELD
    assert classes.count("withheld") == corpus_gate.EXPECTED_WITHHELD == 3
    assert classes.count("failed") == 0
    assert classes.count("validated") + classes.count("review") == corpus_gate.EXPECTED_PASS

    # R-3's registry claims every corpus document, and telemetry sees it.
    assert all(record["dispatch"]["outcome"] == "claimed" for record in records)
    assert all(record["dispatch"]["source"] == "live" for record in records)
    assert all(record["dispatch"]["parser_id"] for record in records)

    # Coverage is computable from these records with the shipped summariser.
    from telemetry.report import summarize

    summary = summarize(records)
    assert summary["total"] == 109
    assert summary["deterministic_coverage"] == 1.0
    assert summary["outcome"]["withheld"] == 3


@pytest.mark.parametrize(
    "rel",
    [
        "Chase/Chase Mar.pdf",
        "Others/IBC/IBC April (1).pdf",
        "Misc/Columbia May 26 complete.pdf",
    ],
)
def test_a_record_leaks_no_customer_data(rel: str):
    """I1, the invariant that makes always-on telemetry safe.

    Checked against the actual document: its filename, its extracted bank
    label, its account number (and every 4+ digit fragment of it), and its
    transaction amounts and descriptions must all be absent from the
    serialized record.
    """
    record, payload = _telemetry_for(rel)
    blob = json.dumps(record, sort_keys=True)
    assert payload is not None

    statement = payload["statement"]
    filename = Path(rel).name

    assert filename not in blob
    assert Path(rel).stem not in blob
    if statement.get("bank"):
        assert statement["bank"] not in blob
    account = statement.get("account_number") or ""
    if account:
        assert account not in blob
        for start in range(0, max(1, len(account) - 3)):
            fragment = account[start:start + 4]
            if fragment.isdigit():
                assert fragment not in blob, f"account fragment {fragment} leaked"

    for transaction in statement.get("transactions", [])[:40]:
        description = (transaction.get("description") or "").strip()
        if len(description) >= 8:
            assert description not in blob
        amount = transaction.get("amount")
        if amount:
            assert f"{abs(amount):.2f}" not in blob

    # Dates from the statement are not recorded either.
    for key in ("period_start", "period_end"):
        if statement.get(key):
            assert statement[key] not in blob


def test_a_record_carries_only_declared_keys():
    """A new field cannot appear without being reviewed against I1."""
    from telemetry import TOP_LEVEL_KEYS

    record, _ = _telemetry_for("Chase/Chase Mar.pdf")
    assert set(record) == set(TOP_LEVEL_KEYS)
    assert set(record["document"]) == {
        "content_sha256", "byte_size", "page_count", "classification", "valid_pdf",
        "encrypted", "malformed_page_count", "likely_account_count",
        "duplicate_of_prior_record",
    }
    assert set(record["outcome"]) == {
        "class", "reason", "escalated", "error_type", "fallback_reason"
    }


def test_truncation_survives_a_cache_round_trip(tmp_path):
    """O-3 x D-3b: the flags are right on a cache hit, not just a fresh read."""
    from webapp.artifact_cache import ArtifactCache, cached_ocr
    from webapp.storage import Storage

    source = CORPUS / "Misc/Columbia May 26 complete.pdf"
    raw = source.read_bytes()
    cache = ArtifactCache(Storage(tmp_path))

    fresh = cached_ocr(
        raw,
        compute=lambda: _tesseract_like_document(raw),
        cache=cache,
        source_file=source.name,
    )
    hit = cached_ocr(
        raw,
        compute=lambda: pytest.fail("cache miss: the second read must be served"),
        cache=cache,
        source_file=source.name,
    )
    assert hit.cached is True
    assert source_section(fresh.value)["truncation"] == source_section(hit.value)["truncation"]


def _tesseract_like_document(raw: bytes):
    """A document with page_integrity, without needing a tesseract binary."""
    from ocr.document import StatementMarkdown
    from ocr.truncation import assess_pages

    pages = ["Statement page one | 100.00", "Statement page two | 200.00"]
    document = StatementMarkdown(
        source_file="columbia.pdf", model="local-tesseract-ocr", pages=pages
    )
    document.page_integrity = assess_pages(pages)
    return document
