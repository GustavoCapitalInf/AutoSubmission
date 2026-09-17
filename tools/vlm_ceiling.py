"""CLI for the Phase 3 ceiling experiment: partitions, run, report. See plan v1 §11 and R16."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ocr.paddle_config import PaddleRefused
from vlm import partitions, report
from vlm.client import StageAWorkerClient, VlmClient
from vlm.receipts import Refused, bound
from vlm.runner import ARMS, RunContext, default_authorize, run_wave
from vlm.truth import ReaderTruth

DEFAULT_STAGE_A_URL = "http://127.0.0.1:18003"
DEFAULT_STAGE_B_URL = "http://127.0.0.1:18002"
DEFAULT_STAGE_B_MODEL = "Qwen/Qwen3.5-4B"
DEFAULT_TRUTH_CACHE = Path(".claude/recovery/webapp_data_train12_cold")
DEFAULT_OUT = Path("discovery_reports/train13-logs/p3ceiling")


def _worker_token(runtime_dir: Path) -> str | None:
    path = runtime_dir / "vlm_worker.token"
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def _run(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    members = partitions.load_private_manifest(manifest_path)
    archive_root = Path(json.loads(manifest_path.read_text(encoding="utf-8"))["archive_root"])
    stage_a = None
    if args.arm in ("stage_a_rules", "hybrid"):
        stage_a = StageAWorkerClient(args.stage_a_url, token=_worker_token(Path(args.runtime_dir)))
    stage_b = VlmClient(args.stage_b_url) if args.arm in ("stage_b_only", "hybrid") else None
    truth = ReaderTruth(Path(args.truth_cache), partitions.DEFAULT_RUN_OF_RECORD) if args.truth else None
    ctx = RunContext(arm=args.arm, stage_a=stage_a, stage_b=stage_b, stage_b_model=args.stage_b_model, truth=truth,
                     long_edge=args.long_edge, quality=args.jpeg_quality, seed=0, data_scope=args.data_scope,
                     hourly_rate=args.hourly_rate, concurrency=args.concurrency)
    try:
        result = run_wave(members, ctx, Path(args.out), archive_root=archive_root, manifest_binding=bound(manifest_path),
                          limit=args.limit, authorize=default_authorize,
                          resume_from=Path(args.resume_from) if args.resume_from else None)
    finally:
        if truth is not None:
            truth.close()
    print(json.dumps({"status": result["status"], "counts": result["counts"], "instance_hours": result["instance_hours"]}))
    return 0 if result["status"] == "complete" else 3


def _preflight(args: argparse.Namespace) -> int:
    """Synthetic pages only (no customer bytes): every arm, one wave each, under the synthetic scope."""
    from datetime import datetime, timezone

    from tests.paddle_synthetic import build_ledger_page, render_image_pdf, render_native_pdf, rotate_page_90
    from vlm.receipts import dump_new

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(args.out) / f"preflight-{stamp}"
    archive = root / "synthetic-archive"
    archive.mkdir(parents=True)
    page = build_ledger_page(n_rows=8)
    docs = {"native": render_native_pdf(page), "image": render_image_pdf(page, dpi=200),
            "rotated": render_native_pdf(rotate_page_90(page))}
    members = []
    for name, raw in docs.items():
        (archive / f"{name}.pdf").write_bytes(raw)
        import hashlib
        members.append({"sha": hashlib.sha256(raw).hexdigest().upper(), "relative_path": f"{name}.pdf", "byte_size": len(raw),
                        "page_count": 1, "folder_label": "synthetic", "classification": "digital", "outcome_class": "synthetic",
                        "account_count": 1})
    manifest = root / "SYNTH.manifest.private.json"
    dump_new(manifest, {"manifest_version": 1, "name": "SYNTH", "set_sha256": "synthetic", "archive_root": str(archive), "members": members})
    codes = {}
    for arm in [a for a in ARMS if a != "reader_baseline"]:
        argv = ["run", "--arm", arm, "--manifest", str(manifest), "--out", str(root / arm), "--data-scope", "synthetic",
                "--stage-a-url", args.stage_a_url, "--stage-b-url", args.stage_b_url, "--stage-b-model", args.stage_b_model,
                "--runtime-dir", args.runtime_dir]
        codes[arm] = main(argv)
        if codes[arm] == 0:
            main(["report", "--wave", str(root / arm)])
    print(json.dumps({"preflight": str(root), "exit_codes": codes}))
    return 0 if all(c == 0 for c in codes.values()) else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vlm_ceiling")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("partitions")
    p.add_argument("--out", default=str(DEFAULT_OUT / "manifests"))
    f = sub.add_parser("preflight")
    f.add_argument("--out", default=str(DEFAULT_OUT / "waves"))
    f.add_argument("--stage-a-url", default=DEFAULT_STAGE_A_URL)
    f.add_argument("--stage-b-url", default=DEFAULT_STAGE_B_URL)
    f.add_argument("--stage-b-model", default=DEFAULT_STAGE_B_MODEL)
    f.add_argument("--runtime-dir", default=".paddle_runtime")
    r = sub.add_parser("run")
    r.add_argument("--arm", choices=ARMS, required=True)
    r.add_argument("--manifest", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--limit", type=int, default=None)
    r.add_argument("--data-scope", choices=("customer", "synthetic"), default="customer")
    r.add_argument("--stage-a-url", default=DEFAULT_STAGE_A_URL)
    r.add_argument("--stage-b-url", default=DEFAULT_STAGE_B_URL)
    r.add_argument("--stage-b-model", default=DEFAULT_STAGE_B_MODEL)
    r.add_argument("--truth", action="store_true")
    r.add_argument("--truth-cache", default=str(DEFAULT_TRUTH_CACHE))
    r.add_argument("--hourly-rate", type=float, default=None)
    r.add_argument("--resume-from", default=None)
    r.add_argument("--long-edge", type=int, default=1540)
    r.add_argument("--jpeg-quality", type=int, default=90)
    r.add_argument("--runtime-dir", default=".paddle_runtime")
    r.add_argument("--concurrency", type=int, default=1, help="Stage B pages in flight per document (server --max-num-seqs bound)")
    q = sub.add_parser("report")
    q.add_argument("--wave", required=True)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "partitions":
            summary = partitions.write_manifests(Path(args.out))
            print(json.dumps({name: {"documents": s["documents"], "pages": s["pages"]} for name, s in summary.items()}))
            return 0
        if args.command == "preflight":
            return _preflight(args)
        if args.command == "run":
            return _run(args)
        if args.command == "report":
            path = report.write_report(Path(args.wave))
            print(json.dumps({"report": str(path)}))
            return 0
    except Refused as exc:
        print(json.dumps({"error": exc.code}))
        return 2
    except PaddleRefused as exc:
        # The reviewed authorization gate refused (opt-in literal absent, scope not authorized): closed code only.
        print(json.dumps({"error": str(exc).split(":", 1)[0]}))
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
