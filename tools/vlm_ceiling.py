"""CLI for the Phase 3 ceiling experiment: partitions, run, report. See plan v1 §11 and R16."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
                     hourly_rate=args.hourly_rate)
    try:
        result = run_wave(members, ctx, Path(args.out), archive_root=archive_root, manifest_binding=bound(manifest_path),
                          limit=args.limit, authorize=default_authorize,
                          resume_from=Path(args.resume_from) if args.resume_from else None)
    finally:
        if truth is not None:
            truth.close()
    print(json.dumps({"status": result["status"], "counts": result["counts"], "instance_hours": result["instance_hours"]}))
    return 0 if result["status"] == "complete" else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vlm_ceiling")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("partitions")
    p.add_argument("--out", default=str(DEFAULT_OUT / "manifests"))
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
    q = sub.add_parser("report")
    q.add_argument("--wave", required=True)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "partitions":
            summary = partitions.write_manifests(Path(args.out))
            print(json.dumps({name: {"documents": s["documents"], "pages": s["pages"]} for name, s in summary.items()}))
            return 0
        if args.command == "run":
            return _run(args)
        if args.command == "report":
            path = report.write_report(Path(args.wave))
            print(json.dumps({"report": str(path)}))
            return 0
    except Refused as exc:
        print(json.dumps({"error": exc.code}))
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
