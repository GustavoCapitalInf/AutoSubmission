"""Private, checksum-bound judgment checks on exactly two or three real PDFs.

Requires --manifest, --manifest-sha256 and --source-root. --output-dir defaults
to judgment-checks under the external private artifact root. Manifest:
{"version":1,"scope":"real_judgment","documents":[
 {"id":"J01","path":"relative.pdf","sha256":"<64 lowercase hex>"}, ...]}.
The caller must already have enabled the explicit remote customer-data opt-in.
Only page images travel through the existing pair HTTP client; no remote files
are created by this tool. Outputs remain private and no webapp job is published.

Native text comparisons are corroboration aids for page review, not ground
truth. Substring matches cannot prove that a description is complete. All
content, reports, native comparisons and receipts stay in the private output.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import sys
from typing import TextIO
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vlm.receipts import Refused, canonical_json, dump_new, need, sha256_bytes, sha256_file, utc_now
from ocr.private_artifacts import (
    PrivateArtifactPathError, private_artifact_path, validate_private_artifact_path,
)
from tools.phase3_pair.check_synthetic import reason_count_report

REPO = Path(__file__).resolve().parents[2]
_ROW_STATES = ("agreed", "corrected", "added", "rejected", "unresolved")


def checked_documents(manifest_path: Path, expected_sha: str, root: Path) -> list[dict]:
    """Bind every input before any model request; resolve symlinks before checks."""
    raw = manifest_path.read_bytes()
    need(sha256_bytes(raw) == expected_sha, "judgment_manifest_changed")
    try:
        manifest = json.loads(raw)
    except (ValueError, TypeError):
        raise Refused("judgment_manifest_invalid") from None
    need(isinstance(manifest, dict) and manifest.get("version") == 1
         and manifest.get("scope") == "real_judgment", "judgment_manifest_scope_invalid")
    entries = manifest.get("documents")
    need(isinstance(entries, list) and 2 <= len(entries) <= 3, "judgment_document_count_invalid")
    source_root = root.resolve(strict=True)
    need(source_root.is_dir(), "judgment_source_root_invalid")
    result, seen_ids, seen_paths, seen_hashes = [], set(), set(), set()
    for item in entries:
        need(isinstance(item, dict) and {"id", "path", "sha256"} <= item.keys(),
             "judgment_document_invalid")
        need(isinstance(item["id"], str) and re.fullmatch(r"J[0-9]{2}", item["id"]) is not None,
             "judgment_document_id_invalid")
        need(isinstance(item["path"], str) and isinstance(item["sha256"], str)
             and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is not None,
             "judgment_document_invalid")
        relative = Path(item["path"])
        need(not relative.is_absolute() and ".." not in relative.parts,
             "judgment_document_path_invalid")
        source = (source_root / relative).resolve(strict=True)
        need(source.is_relative_to(source_root) and source.is_file()
             and source.suffix.lower() == ".pdf", "judgment_document_path_invalid")
        need(item["id"] not in seen_ids and source not in seen_paths
             and item["sha256"] not in seen_hashes, "judgment_document_duplicate")
        need(sha256_file(source) == item["sha256"], "judgment_document_changed")
        with source.open("rb") as handle:
            need(handle.read(4) == b"%PDF", "judgment_document_pdf_required")
        seen_ids.add(item["id"])
        seen_paths.add(source)
        seen_hashes.add(item["sha256"])
        result.append({"id": item["id"], "path": source, "sha256": item["sha256"]})
    return result


def _private_output(path: Path | None, source_root: Path) -> Path:
    from discovery.runner import refuse_production_data_dir

    try:
        target = (private_artifact_path("judgment-checks") if path is None
                  else validate_private_artifact_path(path))
    except PrivateArtifactPathError:
        raise Refused("judgment_output_must_be_private") from None
    refuse_production_data_dir(target)
    root = source_root.resolve()
    need(not target.is_relative_to(root) and not root.is_relative_to(target),
         "judgment_output_overlaps_inputs")
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.chmod(0o700)
    return target


def _write_private(path: Path, value: object) -> None:
    dump_new(path, value)
    path.chmod(0o600)


def _append_ledger(output: Path, entry: dict) -> None:
    ledger = output / "RUN_STATE.md"
    # Only fixed keys, generated run IDs, counters and safe error types enter
    # the ledger; full source details are in the private JSON artifacts.
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write("\n- " + canonical_json(entry) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    ledger.chmod(0o600)


def _native_pages(pdf: Path) -> list[str]:
    import pypdfium2 as pdfium

    texts = []
    with pdfium.PdfDocument(pdf) as document:
        for index in range(len(document)):
            page = document[index]
            try:
                textpage = page.get_textpage()
                try:
                    texts.append(textpage.get_text_range())
                finally:
                    textpage.close()
            finally:
                page.close()
    return texts


def _matches(description: object, text: str | None) -> dict:
    available = bool(text and text.strip()) and isinstance(description, str) and bool(description.strip())
    return {
        "available": available,
        "exact_substring": description in text if available else None,
        "whitespace_only_substring": " ".join(description.split()) in " ".join(text.split())
        if available else None,
    }


def compare_descriptions(pair: dict, page_texts: list[str]) -> dict:
    counts = Counter({name: 0 for name in (
        "corrected", "corrections_supported", "corrections_damaged", "corrections_indeterminate",
        "corrected_description_unchanged", "agreed", "agreed_native_unavailable",
        "agreed_exact_mismatched", "agreed_whitespace_mismatched")})
    rows = []
    for index, row in enumerate(pair.get("row_evidence", [])):
        page = row.get("page")
        text = page_texts[page - 1] if isinstance(page, int) and 1 <= page <= len(page_texts) else None
        original = (row.get("original") or {}).get("description")
        reviewed = (row.get("row") or row.get("corrected") or {}).get("description")
        before, after = _matches(original, text), _matches(reviewed, text)
        state = row.get("state")
        conclusion = None
        if state == "corrected":
            counts["corrected"] += 1
            counts["corrected_description_unchanged"] += original == reviewed
            conclusion = "indeterminate"
            if before["available"] and after["available"]:
                old, new = before["whitespace_only_substring"], after["whitespace_only_substring"]
                if new and not old:
                    conclusion = "supported"
                elif old and not new:
                    conclusion = "damaged"
            counts["corrections_" + conclusion] += 1
        elif state == "agreed":
            counts["agreed"] += 1
            counts["agreed_native_unavailable"] += not after["available"]
            counts["agreed_exact_mismatched"] += after["exact_substring"] is False
            counts["agreed_whitespace_mismatched"] += after["whitespace_only_substring"] is False
        rows.append({"row_index": index, "candidate_id": row.get("candidate_id"), "page": page,
                     "state": state, "original": before, "reviewed": after,
                     "description_changed": original != reviewed,
                     "description_change_corroboration": conclusion})
    return {"method": "same_page_native_exact_and_whitespace_substring_v1",
            "limitations": "Native text is not ground truth; substring matches do not establish completeness. "
                           "Amount/date corrections and reading quality require page review.",
            "native_pages": len(page_texts),
            "native_pages_with_text": sum(bool(text.strip()) for text in page_texts),
            "counts": dict(counts), "rows": rows}


def printed_field_presence(pair: dict) -> dict:
    """Preserve absent/unknown evidence; never derive missing source anchors."""
    statement = pair.get("statement") or {}
    fields = ("period_start", "period_end", "beginning_balance", "ending_balance")
    present = {field: statement.get(field) is not None for field in fields}
    for item in pair.get("field_evidence", []):
        if item.get("field") in present and item.get("value") is not None:
            present[item["field"]] = True
    # An unadmitted statement may lack serialized daily snapshots entirely;
    # absence of that evidence is unknown, not a claim the source has none.
    daily = statement.get("stated_daily_balances")
    snapshot_count = pair.get('source_daily_balance_count')
    if type(snapshot_count) is not int or snapshot_count < 0:
        snapshot_count = None
    ledger = statement.get("transactions")
    retained = sum(row.get("state") in {"agreed", "corrected", "added"}
                   for row in pair.get("row_evidence", []))
    return {"printed_fields_present": present,
            "missing_printed_fields": [field for field, seen in present.items() if not seen],
            "transaction_ledger_count": len(ledger) if isinstance(ledger, list) else retained,
            "daily_balance_snapshot_count": len(daily) if isinstance(daily, list) else snapshot_count,
            "computed_daily_ledger_count": None,
            "usable_daily_ledger": None if pair.get("gate", {}).get("admitted") else False}


def _progress(console: TextIO, document_id: str):
    def emit(event: str) -> None:
        if event in {"visual_pair_rendering", "visual_pair_gating"}:
            payload = {"document_id": document_id, "stage": event.removeprefix("visual_pair_")}
        else:
            match = re.fullmatch(r"visual_pair_(proposing|reviewing):([0-9]+)/([0-9]+)(?::(batch|crop):([0-9]+)/([0-9]+)|:(discovery))?", event)
            if match is None:
                return
            payload = {"document_id": document_id, "stage": match[1],
                       "page": int(match[2]), "pages": int(match[3])}
            if match[4]:
                payload.update(part_type=match[4], part=int(match[5]), parts=int(match[6]))
            elif match[7]:
                payload['part_type'] = 'discovery'
        print(canonical_json(payload), file=console, flush=True)
    return emit


def _run_document(item: dict, *, output: Path, evidence: Path, settings, console: TextIO) -> dict:
    from analysis.serialization import document_report_to_dict
    from vlm.pair import extract_visual_pair
    from vlm.pair_adapter import analyze_visual_pair

    document_id = item["id"]
    result = {"document_id": document_id, "pages": 0, "gate_admitted": False,
              "status": "extraction_failed", "counts": {}, "error_type": None,
              "gate_reason_count": None, "gate_reason_counts": None}
    try:
        # Recheck immediately before this input is opened; the full batch was
        # also checked before the first model call.
        need(sha256_file(item["path"]) == item["sha256"], "judgment_document_changed")
        doc = extract_visual_pair(item["path"], settings=settings, evidence_dir=evidence,
                                  progress=_progress(console, document_id), data_scope="customer")
        pair = doc.visual_pair
        _write_private(output / (document_id + "-document.private.json"), {
            "pdf_sha256": item["sha256"], "source_file": doc.source_file, "model": doc.model,
            "pages": doc.pages, "page_integrity": [asdict(v) for v in doc.page_integrity],
            "visual_pair": pair})
        result.update(pages=len(doc.pages), gate_admitted=bool(pair["gate"]["admitted"]),
                      **reason_count_report(pair["gate"]),
                      counts={name: pair["confidence"]["counts"].get(name, 0) for name in _ROW_STATES},
                      status="gate_refused", fields=printed_field_presence(pair))
        try:
            checks = compare_descriptions(pair, _native_pages(item["path"]))
            _write_private(output / (document_id + "-native-check.private.json"), checks)
            result["native_description_checks"] = checks["counts"]
        except Exception as exc:
            result["native_check_error_type"] = type(exc).__name__
        if result["gate_admitted"]:
            result["status"] = "analysis_failed"
            # Offline evaluation only: no job publication and no env mutation.
            report = analyze_visual_pair(doc, review_policy="admit_gated")
            _write_private(output / (document_id + "-analysis.private.json"), document_report_to_dict(report))
            ledgers = [account.metrics.adb for account in report.accounts]
            result["fields"]["computed_daily_ledger_count"] = sum(
                len(ledger.daily_balances) if ledger is not None else 0 for ledger in ledgers)
            result["fields"]["usable_daily_ledger"] = bool(report.accounts) and all(
                account.metrics.adb_ok is True and account.metrics.adb is not None
                and bool(account.metrics.adb.daily_balances) for account in report.accounts)
            result["status"] = "analysis_completed"
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    print(canonical_json(result), file=console, flush=True)
    return result


def run(args: argparse.Namespace) -> dict:
    from ocr.visual_pair_config import check_remote_authorization, load_visual_pair_settings

    output = _private_output(args.output_dir, args.source_root)
    run_id = uuid4().hex
    started = utc_now()
    _append_ledger(output, {"run_id": run_id, "at": started, "status": "started",
                            "scope": "real_judgment"})
    try:
        documents = checked_documents(args.manifest, args.manifest_sha256, args.source_root)
        settings = load_visual_pair_settings()
        for item in documents:
            check_remote_authorization(settings, data_scope="customer", pdf_sha256=item["sha256"])
        folder = output / run_id
        folder.mkdir(mode=0o700)
        _write_private(folder / "manifest.private.json", json.loads(args.manifest.read_bytes()))
        # Library diagnostics may contain input text. Retain them privately;
        # our own output callback uses the original console and closed fields.
        console = sys.stdout
        with (folder / "diagnostics.private.log").open("x", encoding="utf-8") as diagnostics:
            (folder / "diagnostics.private.log").chmod(0o600)
            with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
                results = [_run_document(item, output=folder, evidence=output / "evidence",
                                         settings=settings, console=console) for item in documents]
        counts: Counter = Counter()
        for result in results:
            counts.update(result["counts"])
        summary = {"version": 1, "run_id": run_id, "started": started, "finished": utc_now(),
                   "scope": "real_judgment", "manifest_sha256": args.manifest_sha256,
                   "documents": len(results), "pages": sum(item["pages"] for item in results),
                   "admitted": sum(item["gate_admitted"] for item in results),
                   "analyzed": sum(item["status"] == "analysis_completed" for item in results),
                   "counts": dict(counts), "runs": results,
                   "gate_checks": [{key: item[key] for key in
                                    ("document_id", "gate_reason_count", "gate_reason_counts")}
                                   for item in results],
                   "assessment": "Private judgment aids only; page review required, no quality score or publication."}
        _write_private(folder / "summary.private.json", summary)
        _append_ledger(output, {"run_id": run_id, "at": summary["finished"], "status": "finished",
                               **{key: summary[key] for key in ("documents", "pages", "admitted", "analyzed", "counts")}})
        return summary
    except Exception as exc:
        _append_ledger(output, {"run_id": run_id, "at": utc_now(), "status": "failed",
                               "error_type": type(exc).__name__})
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path,
                        help="absolute external output directory (default: private root/judgment-checks)")
    args = parser.parse_args(argv)
    try:
        summary = run(args)
    except Exception as exc:
        print(canonical_json({"status": "failed", "error_type": type(exc).__name__}), flush=True)
        return 1
    print(canonical_json({key: summary[key] for key in
                          ("documents", "pages", "admitted", "analyzed", "counts", "gate_checks")}), flush=True)
    return 0 if summary["analyzed"] == summary["documents"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
