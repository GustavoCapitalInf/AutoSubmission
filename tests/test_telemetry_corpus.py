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
from corpus_artifacts import cached_markdown, cached_pages
from ocr.inspect import inspect_pdf
from telemetry import (
    VOCABULARY,
    DispatchCollector,
    StageTimer,
    build_record,
    diagnose,
    dispatch_section,
    document_section,
    empty_diagnostics,
    model_calls_for,
    score_vector,
    source_section,
)
from telemetry.report import diagnostics_rollup, render_diagnostics

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

#: W3-2. The diagnosis each withheld statement must produce, taken from the
#: forensic evidence in `docs/adb-withheld-second-pass.md` — not from a run.
#:
#: - Ace: "the supplied PDF has incomplete transaction detail" — 11 of 26
#:   checks/debits are visible, so the coverage check is the CAUSE and the
#:   ledger identity that fails on top of it is the symptom.
#: - BMO: "mutually contradictory financial records" — the two page summaries
#:   disagree with each other and with the row amounts; the bmo registration's
#:   integrity check proves it, which is exactly `source_contradiction`.
#: - IBC: the bank's own summary block does not satisfy its own identity
#:   (`summary_math_inconsistent`), which is upstream of everything the
#:   detail then fails.
WITHHELD_DIAGNOSIS = {
    "Ace_Auto_Final_Cut.pdf": "detail_coverage",
    "BMO_Statement_January_2026 Final-1-2 (1).pdf": "source_contradiction",
    "IBC April (1).pdf": "summary_identity",
}

#: Manifest-relative paths of the same three, for the tests that resolve them
#: directly rather than walking the manifest.
WITHHELD_PATHS = (
    "Misc/Ace_Auto_Final_Cut.pdf",
    "Others/BMO/BMO_Statement_January_2026 Final-1-2 (1).pdf",
    "Others/IBC/IBC April (1).pdf",
)

#: The check-level evidence each must carry, over and above the primary class.
WITHHELD_REQUIRED_CODES = {
    "Ace_Auto_Final_Cut.pdf": {
        "recon:sum_check_failed",
        "recon:debit_coverage_short",
        "integrity:debit_detail_coverage_mismatch",
        "adb:ledger_reconciles_to_closing",
        "adb:final_balance_matches_statement_closing",
    },
    # `integrity:missing_declared_statement_page` was here until WIRING-2's
    # approved ceremony withdrew it: the statement supplies 2 text-bearing
    # sheets for the 2 pages it declares, so no page was ever absent. The
    # document stays withheld on the contradiction its other codes carry.
    "BMO_Statement_January_2026 Final-1-2 (1).pdf": {
        "integrity:conflicting_statement_summaries",
        "recon:running_balance_break",
        "recon:credit_coverage_short",
        "recon:debit_coverage_short",
        "adb:running_balances_support_daily_ledger",
        "adb:ledger_reconciles_to_closing",
    },
    "IBC April (1).pdf": {
        "recon:summary_identity_failed",
        "integrity:summary_math_inconsistent",
        "recon:running_balance_break",
        "adb:ledger_reconciles_to_closing",
    },
}

#: COUNTS-P2 widened `DIAGNOSABLE_CLASSES` to `review`, so the pinned corpus's
#: six review documents are diagnosed too. They are enumerated rather than
#: counted because this is the anchor that says phase 2 moved nothing: every
#: one of them is in `review` for a reason that predates the count check, and
#: none of them carries a count code.
#
# Six until WIRING-2's approved ceremony: Texas Bank and Regions were diagnosed
# `page_coverage` on a flag that was FALSE — their pages are present as
# unlabelled sheets — and both now publish as validated with no diagnosis at
# all. The three that remained kept theirs, each because a page really is
# unaccounted for.
#
# Three, since W3 §REPAIRDOC: `Columbia May 26 complete.pdf` was the fourth and
# is now a pinned REFUSAL (`corpus_gate.PINNED_REFUSALS`). Its page is still
# unaccounted for; there is simply no published statement left for the finding
# to sit on, which is what a refusal means.
REVIEW_DIAGNOSIS = {
    # a transaction export, not a bank statement — a document class, which is
    # why its evidence is all advisory
    "Chase Business.pdf": "advisory_only",
    # the statement declares bank pages the supplied PDF does not contain
    "Builder June 2026.pdf": "page_coverage",
    "Link Bank April statement.pdf": "page_coverage",
}

#: The count check's entire footprint on the pinned 109: ONE code, on a
#: document that was already withheld and already diagnosed `detail_coverage`
#: for the same cause (11 of the bank's 26 stated checks/debits are in the
#: supplied PDF, so the debit COUNT is short exactly as the debit MONEY is).
#: The code adds evidence to an existing diagnosis and changes no class.
COUNT_CODES = {"integrity:credit_count_mismatch", "integrity:debit_count_mismatch"}
COUNT_CODE_DOCUMENTS = {"Ace_Auto_Final_Cut.pdf": {"integrity:debit_count_mismatch"}}


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

    The intake page list is supplied exactly when production supplies it, read
    off `corpus_gate.PRODUCTION_SUPPLIES_SHEETS` rather than restated here.
    This anchor is a harness like the gate's, and it carries the same trap: one
    that analyses differently from production pins an outcome production never
    publishes, and one that stays unwired after production is wired goes
    silently blind on the flag it exists to watch. There is exactly one
    declaration of what the callers do, and both harnesses read it.
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
        if doc is not None:
            markdown, pages = doc.to_markdown(), list(doc.pages)
        else:
            markdown, pages = cached_markdown(raw, CACHE), cached_pages(raw, CACHE)
    sheets = pages if corpus_gate.PRODUCTION_SUPPLIES_SHEETS else None
    payload, error_type, escalated = None, None, False
    try:
        with timer.time("analysis", "miss"):
            report = analyze_markdown(
                markdown, parse_mode="deterministic", on_dispatch=collector,
                sheets=sheets,
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
            collector.dispatch, scores, registration_count, payload=payload,
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
    """The 105/3/1 anchor, from an independent code path.

    The corpus gate proves 105 PASS / 3 WITHHELD / 1 REFUSED by re-running two forensic
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
    failed = {
        Path(rel).name
        for rel, record in zip(manifest, records)
        if record["outcome"]["class"] == "failed"
    }
    assert withheld == WITHHELD
    assert classes.count("withheld") == corpus_gate.EXPECTED_WITHHELD == 3
    # W3 §REPAIRDOC: one pinned document publishes nothing at all. `failed`
    # here is the same fact `corpus_gate.PINNED_REFUSALS` pins, seen from the
    # telemetry side, and the two are tied together by name below so a second
    # refusal cannot appear here without appearing there.
    assert failed == {Path(rel).name for rel in corpus_gate.PINNED_REFUSALS}
    assert classes.count("failed") == corpus_gate.EXPECTED_REFUSED == 1
    assert classes.count("validated") + classes.count("review") == corpus_gate.EXPECTED_PASS

    # R-3's registry claims every corpus document it publishes, and telemetry
    # sees it. The refusal is `unclaimed`, with no parser named: the reader
    # DETECTED it and then declined, which is a different fact and is carried
    # by `attempted` rather than by `parser_id`.
    unclaimed = [record for record in records if record["dispatch"]["outcome"] != "claimed"]
    assert len(unclaimed) == corpus_gate.EXPECTED_REFUSED
    assert [record["dispatch"]["outcome"] for record in unclaimed] == ["unclaimed"]
    assert all(record["dispatch"]["source"] == "live" for record in records)
    assert all(
        record["dispatch"]["parser_id"]
        for record in records
        if record["dispatch"]["outcome"] == "claimed"
    )

    # Coverage is computable from these records with the shipped summariser.
    from telemetry.report import summarize

    summary = summarize(records)
    assert summary["total"] == 109
    assert summary["coverage"]["numerator"] == 108
    assert summary["coverage"]["denominator"] == 109
    assert summary["deterministic_coverage"] == 108 / 109
    assert summary["outcome"]["withheld"] == 3
    assert summary["outcome"]["failed"] == 1


@pytest.mark.corpus
def test_withheld_diagnostics_reproduce_the_documented_diagnosis():
    """W3-2's anchor: the refused and the flagged are diagnosed; the published
    are not.

    The diagnosis is the one `docs/adb-withheld-second-pass.md` established
    forensically from the PDF bytes, so this asserts that the taxonomy reaches
    the human conclusion from the product's own serialized payload — and that
    it stays silent on every document the platform published without
    question, which is what keeps "why was this withheld" from becoming noise
    on 100 healthy files.

    COUNTS-P2 widened the diagnosable scope from `withheld` to
    `withheld | review`, so the property changed shape and is restated rather
    than relaxed: it was "the 106 produce empty diagnostics" and it is now
    "the VALIDATED produce empty diagnostics", with the review documents
    enumerated in `REVIEW_DIAGNOSIS`. The gate's own PASS count was untouched
    by WIRING-2's ceremony — 106 PASS = 102 validated + 4 review, where it was
    100 + 6 — and W3 §REPAIRDOC moved it for the first time, to 105 = 102 + 3,
    by taking one document out of the published set altogether. This test
    asserts that identity directly so the two vocabularies stay tied together. The split moving inside PASS while the
    oracles' own number does not is precisely the blindness the gate's verdict
    check was added to close.
    """
    manifest = _manifest()
    records = [_telemetry_for(rel)[0] for rel in manifest]

    diagnosed, review, refused, quiet = {}, {}, {}, 0
    for rel, record in zip(manifest, records):
        section = record["diagnostics"]
        outcome = record["outcome"]["class"]
        if outcome == "withheld":
            diagnosed[Path(rel).name] = section
        elif outcome == "review":
            review[Path(rel).name] = section
        elif outcome == "failed":
            refused[Path(rel).name] = section
        else:
            assert outcome == "validated", rel
            assert section == empty_diagnostics(), rel
            quiet += 1

    assert quiet == 102
    assert quiet + len(review) == corpus_gate.EXPECTED_PASS == 105
    assert set(diagnosed) == WITHHELD
    # W3 §REPAIRDOC. A pinned refusal published no payload, so there is nothing
    # for the taxonomy to read and its section is empty — the diagnosis of a
    # document that produced no analysis is the refusal itself, which
    # `corpus_gate.PINNED_REFUSALS` carries.
    assert set(refused) == {Path(rel).name for rel in corpus_gate.PINNED_REFUSALS}

    # The review population, enumerated: every one of them is here for a
    # reason that predates the count check.
    assert {name: section["primary_class"] for name, section in review.items()} == REVIEW_DIAGNOSIS
    for name, section in review.items():
        assert section["evaluated"] is True
        assert section["codes"], name
        assert not COUNT_CODES & set(section["codes"]), name

    # The count check's whole footprint on the pinned 109.
    carrying = {
        name: COUNT_CODES & set(section["codes"])
        for name, section in {**diagnosed, **review}.items()
        if COUNT_CODES & set(section["codes"])
    }
    assert carrying == COUNT_CODE_DOCUMENTS

    for name, section in diagnosed.items():
        assert section["evaluated"] is True
        assert section["primary_class"] == WITHHELD_DIAGNOSIS[name], name
        # W3-2b re-baselined the class ranking by inserting `check_unavailable`
        # above the financial classes. The pinned three are unaffected, and
        # this says so rather than leaving it to be inferred: none of them had
        # an integrity check crash, so none of their diagnoses is incomplete.
        assert "check_unavailable" not in section["classes"], name
        assert "integrity:integrity_check_exception" not in section["codes"], name
        assert WITHHELD_REQUIRED_CODES[name] <= set(section["codes"]), name
        assert section["unmapped"] == [], name
        assert section["counts"]["unmapped_reconciliation_issues"] == 0, name
        assert section["counts"]["unmapped_adb_warnings"] == 0, name
        assert set(section["codes"]) <= set(VOCABULARY), name

    # The rollup answers the W3-2 question in one call over the same records.
    rollup = diagnostics_rollup(records)
    assert rollup["total"] == 109
    assert rollup["diagnosed"] == 6  # the 3 withheld + the 3 review
    assert rollup["classes"] == {
        "source_contradiction": 1, "summary_identity": 1, "detail_coverage": 1,
        # 5 until WIRING-2's ceremony withdrew two FALSE page_coverage
        # diagnoses; 3 until W3 §REPAIRDOC took a third page_coverage document
        # out of the published set. A refusal has no payload, so the taxonomy
        # has nothing to read and it is not `diagnosed` — the refusal itself is
        # the diagnosis, and `corpus_gate.PINNED_REFUSALS` is where it lives.
        "page_coverage": 2, "advisory_only": 1,
    }
    assert rollup["diagnosed"] == len(diagnosed) + len(review)
    assert rollup["total"] - rollup["diagnosed"] == quiet + len(refused)
    # One count code in the whole pinned corpus, on the document whose debit
    # detail the gate already refuses.
    assert rollup["codes"]["integrity:debit_count_mismatch"] == 1
    assert "integrity:credit_count_mismatch" not in rollup["codes"]
    assert rollup["unmapped"] == {
        "names": {}, "reconciliation_issues": 0, "adb_warnings": 0,
    }
    assert render_diagnostics(rollup, "corpus-anchor").isascii()


def test_diagnostics_change_no_analysis_output():
    """Diagnostics are a read-only projection, proven on real documents.

    The payload the collector diagnoses must be byte-identical afterwards —
    the corpus gate's byte-identical authority applied to the one new thing
    W3-2 introduced.
    """
    import json as _json

    for rel in sorted(WITHHELD_PATHS):
        record, payload = _telemetry_for(rel)
        assert payload is not None
        before = _json.dumps(payload, sort_keys=True, default=str)
        diagnose(payload, record["outcome"]["class"])
        assert _json.dumps(payload, sort_keys=True, default=str) == before, rel


#: Record fields that are machine-generated identifiers, not projections of
#: anything in the document: a uuid4, a wall-clock timestamp, the run label,
#: and the content hash (which I1 explicitly admits). They are high-entropy
#: digit strings, so leaving them in the substring scan below makes it
#: coincidence-prone rather than strict — `emitted_at` "…:58:51.752210" reads
#: as the amount 51.75. `test_the_identity_fields_are_what_they_claim_to_be`
#: pins each of them by shape instead, so nothing goes unchecked.
_NOT_DOCUMENT_DERIVED = ("record_id", "emitted_at", "run_id")


def _scannable(record: dict) -> dict:
    scrubbed = {k: v for k, v in record.items() if k not in _NOT_DOCUMENT_DERIVED}
    scrubbed["document"] = {
        k: v for k, v in record["document"].items() if k != "content_sha256"
    }
    return scrubbed


def test_the_identity_fields_are_what_they_claim_to_be():
    """The four fields `_scannable` removes are pinned here, by shape.

    So the scrub narrows the substring scan without narrowing the invariant.
    """
    import re
    import uuid

    raw = (CORPUS / "Chase/Chase Mar.pdf").read_bytes()
    record, _ = _telemetry_for("Chase/Chase Mar.pdf")

    assert uuid.UUID(hex=record["record_id"])
    assert record["run_id"] == "corpus-anchor"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T[\d:.]+\+00:00", record["emitted_at"])
    assert record["document"]["content_sha256"] == inspect_pdf(raw).content_sha256


@pytest.mark.parametrize(
    "rel",
    [
        "Chase/Chase Mar.pdf",
        "Others/IBC/IBC April (1).pdf",
        # A SCANNED statement, so the invariant is proven over OCR text too.
        # It was the Columbia statement until W3 §REPAIRDOC made that document
        # a pinned refusal: a record with no payload cannot demonstrate that a
        # PUBLISHED record leaks nothing.
        "Misc/First Farmers 2026 01-document.pdf",
    ],
)
def test_a_record_leaks_no_customer_data(rel: str):
    """I1, the invariant that makes always-on telemetry safe.

    Checked against the actual document: its filename, its extracted bank
    label, its account number (and every 4+ digit fragment of it), and its
    transaction amounts and descriptions must all be absent from the
    serialized record.

    `IBC April (1).pdf` is in the parameter list on purpose: it is one of the
    three withheld statements, so this runs with the W3-2 diagnostics section
    POPULATED from reconciliation issues and ADB warnings — the two free-text
    sources in the whole payload that quote descriptions, amounts and dates.
    An assertion below pins that, so the sensitivity proof can never quietly
    degrade to checking an empty section.
    """
    record, payload = _telemetry_for(rel)
    assert payload is not None
    if record["outcome"]["class"] == "withheld":
        assert record["diagnostics"]["evaluated"] is True
        assert record["diagnostics"]["codes"]

    blob = json.dumps(_scannable(record), sort_keys=True)
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
    assert set(record["diagnostics"]) == {
        "evaluated", "diagnostics_version", "primary_class", "classes", "codes",
        "adb_checks_failed", "integrity_flags", "summary_fields_absent",
        "counts", "unmapped",
        # MAJOR-3 (PHASE2_P20SEAM_REVIEW.md): added by `build_record`
        # alongside `diagnose_document`'s own closed taxonomy, not inside it
        # — see `telemetry/record.py::build_record`'s "diagnostics" comment.
        "source_path_unrecognized_model",
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
