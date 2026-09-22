"""Run the pair only on a checksum-bound manifest of fabricated PDF fixtures.

The manifest is supplied explicitly and its own SHA256 is required. Its shape:
{"version":1,"data_scope":"synthetic","files":[{"path":"pdfs/example.pdf",
"sha256":"<64 hex characters>"}]}. The supplied fixture manifest is also
accepted as {"manifest_version":1,"scope":"synthetic","docs":[
{"source_rel":"example.pdf","source_sha256":"<64 hex characters>",...}]}.
Paths in either format are relative to --synthetic-root.
--output-dir defaults to synthetic-checks under the external private artifact root.
All inputs are verified before the first request. Standard output contains only
counts/status; complete source evidence and the append-only ledger stay private.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vlm.receipts import Refused, canonical_json, dump_new, need, sha256_bytes, sha256_file, utc_now
from ocr.private_artifacts import (
    PrivateArtifactPathError, private_artifact_path, validate_private_artifact_path,
)


def reason_count_report(gate: dict) -> dict:
    """Copy only reason codes and integer counters into shared CLI output.

    Missing or incomplete legacy metadata has unknown counts, never one count
    inferred from a compatibility reason flag.
    """
    from vlm.gate import REASONS

    unavailable = {"gate_reason_count": None, "gate_reason_counts": None}
    raw = gate.get("reason_counts")
    reasons = gate.get("reasons", [])
    if not isinstance(raw, dict) or not isinstance(reasons, list):
        return unavailable
    if any(not isinstance(code, str) or code not in REASONS for code in reasons):
        return unavailable
    if not set(reasons).issubset(raw):
        return unavailable
    counts = {}
    for code, item in raw.items():
        if code not in REASONS or not isinstance(item, dict):
            return unavailable
        total, document, pages = (item.get(key) for key in ("count", "document_count", "pages"))
        if (type(total) is not int or total < 0 or type(document) is not int or document < 0
                or not isinstance(pages, list)):
            return unavailable
        by_page = {}
        for page_count in pages:
            if not isinstance(page_count, dict):
                return unavailable
            page, number = page_count.get("page"), page_count.get("count")
            if (type(page) is not int or page < 1 or type(number) is not int or number < 1
                    or page in by_page):
                return unavailable
            by_page[page] = number
        if sum(by_page.values()) + document != total:
            return unavailable
        counts[code] = {"count": total,
                        "pages": [{"page": page, "count": number} for page, number in sorted(by_page.items())],
                        "document_count": document}
    return {"gate_reason_count": sum(item["count"] for item in counts.values()),
            "gate_reason_counts": counts}


def checked_fixtures(manifest_path: Path, expected_sha: str, root: Path) -> list[Path]:
    raw = manifest_path.read_bytes()
    need(sha256_bytes(raw) == expected_sha, "synthetic_manifest_changed")
    try:
        manifest = json.loads(raw)
    except (ValueError, TypeError):
        raise Refused("synthetic_manifest_invalid") from None
    need(isinstance(manifest, dict), "synthetic_manifest_scope_invalid")
    simple_keys = {"version", "data_scope", "files"}
    supplied_keys = {"manifest_version", "scope", "docs"}
    if simple_keys <= manifest.keys() and not supplied_keys.intersection(manifest):
        need(manifest["version"] == 1 and manifest["data_scope"] == "synthetic",
             "synthetic_manifest_scope_invalid")
        entries = manifest["files"]
    elif supplied_keys <= manifest.keys() and not simple_keys.intersection(manifest):
        need(manifest["manifest_version"] == 1 and manifest["scope"] == "synthetic",
             "synthetic_manifest_scope_invalid")
        docs = manifest["docs"]
        need(isinstance(docs, list), "synthetic_fixture_count_invalid")
        entries = []
        for doc in docs:
            need(isinstance(doc, dict) and {"source_rel", "source_sha256"} <= doc.keys(),
                 "synthetic_fixture_invalid")
            # Other fields in the frozen fixture manifest describe its
            # generation and rendered pages. Only these two bind an input.
            entries.append({"path": doc["source_rel"], "sha256": doc["source_sha256"]})
    else:
        raise Refused("synthetic_manifest_scope_invalid")
    need(isinstance(entries, list) and 1 <= len(entries) <= 3, "synthetic_fixture_count_invalid")
    source_root = root.resolve(strict=True)
    checked = []
    seen = set()
    for item in entries:
        need(isinstance(item, dict) and set(item) == {"path", "sha256"}, "synthetic_fixture_invalid")
        need(isinstance(item["path"], str) and isinstance(item["sha256"], str)
             and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is not None,
             "synthetic_fixture_invalid")
        relative = Path(item["path"])
        need(not relative.is_absolute(), "synthetic_fixture_path_invalid")
        source = (source_root / relative).resolve(strict=True)
        need(source.is_relative_to(source_root) and source.suffix.lower() == ".pdf",
             "synthetic_fixture_path_invalid")
        need(source not in seen, "synthetic_fixture_duplicate")
        need(sha256_file(source) == item["sha256"], "synthetic_fixture_changed")
        need(source.read_bytes().startswith(b"%PDF"), "synthetic_fixture_pdf_required")
        seen.add(source)
        checked.append(source)
    return checked


def _private_output(path: Path | None, source_root: Path) -> Path:
    from discovery.runner import refuse_production_data_dir

    try:
        target = (private_artifact_path("synthetic-checks") if path is None
                  else validate_private_artifact_path(path))
    except PrivateArtifactPathError:
        raise Refused("synthetic_output_must_be_private") from None
    refuse_production_data_dir(target)
    root = source_root.resolve()
    need(not target.is_relative_to(root) and not root.is_relative_to(target),
         "synthetic_output_overlaps_inputs")
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.chmod(0o700)
    return target


def run(args: argparse.Namespace) -> dict:
    from ocr.visual_pair_config import load_visual_pair_settings
    from vlm.pair import extract_visual_pair
    from vlm.pair_adapter import VisualPairAdmissionError, analyze_visual_pair

    fixtures = checked_fixtures(args.manifest, args.manifest_sha256, args.synthetic_root)
    output = _private_output(args.output_dir, args.synthetic_root)
    settings = load_visual_pair_settings()
    started = utc_now()
    counts: Counter[str] = Counter()
    details = []
    for index, fixture in enumerate(fixtures, 1):
        try:
            doc = extract_visual_pair(fixture, settings=settings, evidence_dir=output / "evidence",
                                      data_scope="synthetic")
        except Exception as exc:
            failed = {"fixture_index": index, "pdf_sha256": sha256_file(fixture),
                      "pages": 0, "status": "extraction_failed", "gate_admitted": False,
                      "gate_reasons": [], "counts": {}, "analysis_path": None,
                      "gate_reason_count": None, "gate_reason_counts": None,
                      "receipt_sha256": None, "error_type": type(exc).__name__}
            details.append(failed)
            print(canonical_json({key: failed[key] for key in
                                  ("fixture_index", "status", "error_type", "gate_reason_count", "gate_reason_counts")}), flush=True)
            continue
        pair = doc.visual_pair
        gate = pair["gate"]
        state_counts = pair["confidence"]["counts"]
        counts.update(state_counts)
        status = "gate_refused"
        analysis_path = None
        if gate["admitted"]:
            try:
                # This explicit admission is scoped to verified fabricated
                # fixtures. It changes no webapp configuration or user policy.
                report = analyze_visual_pair(doc, review_policy="admit_gated")
                status = "analysis_completed"
                analysis_path = "bank_bridge" if report.accounts[0].model_used.endswith("-bank-bridge") else "generic"
            except VisualPairAdmissionError:
                status = "analysis_refused"
        details.append({"fixture_index": index, "pdf_sha256": sha256_file(fixture),
                        "pages": len(doc.pages), "status": status,
                        "gate_admitted": gate["admitted"], "gate_reasons": gate["reasons"],
                        **reason_count_report(gate),
                        "counts": state_counts, "analysis_path": analysis_path,
                        "receipt_sha256": pair["receipt_sha256"]})
        print(canonical_json({key: details[-1][key] for key in
                              ("fixture_index", "pages", "status", "counts", "gate_reason_count", "gate_reason_counts")}), flush=True)
    summary = {"version": 1, "started": started, "finished": utc_now(),
               "scope": "synthetic_wiring_only", "manifest_sha256": args.manifest_sha256,
               "documents": len(details), "pages": sum(item["pages"] for item in details),
               "admitted": sum(item["gate_admitted"] for item in details),
               "analyzed": sum(item["status"] == "analysis_completed" for item in details),
               "counts": dict(counts), "runs": details,
               "gate_checks": [{key: item[key] for key in
                                ("fixture_index", "gate_reason_count", "gate_reason_counts")}
                               for item in details]}
    digest = sha256_bytes(canonical_json(summary).encode())
    record = output / ("synthetic-check-" + digest + ".json")
    dump_new(record, summary)
    record.chmod(0o600)
    ledger = output / "RUN_STATE.md"
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(f"\n- {summary['finished']} synthetic wiring: {summary['documents']} document(s), "
                     f"{summary['pages']} page(s), {summary['admitted']} gate-admitted, "
                     f"{summary['analyzed']} analyzed; row states {canonical_json(dict(counts))}; "
                     f"receipt {digest}. Fabricated fixtures only; no reading-quality conclusion.\n")
        handle.flush()
        os.fsync(handle.fileno())
    ledger.chmod(0o600)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--synthetic-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path,
                        help="absolute external output directory (default: private root/synthetic-checks)")
    args = parser.parse_args(argv)
    try:
        summary = run(args)
    except Exception as exc:
        # Even fixture content stays out of a shared console. Detailed model
        # evidence is already receipted privately by the extractor.
        print(canonical_json({"status": "failed", "error_type": type(exc).__name__}), flush=True)
        return 1
    print(canonical_json({key: summary[key] for key in
                          ("documents", "pages", "admitted", "analyzed", "counts", "gate_checks")}), flush=True)
    return 0 if summary["analyzed"] == summary["documents"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
