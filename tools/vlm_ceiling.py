"""CLI for the Phase 3 ceiling experiment: partitions, preflight, run, report. See plan v1 §11 and R16.

Review closures: BLOCK-3 (the data scope comes from the manifest, never from a flag), MAJOR-7 (the fetch
receipts are bound into launch.json as the weights pin), MINOR-6 (`report --exclude-manifest` reports the
slice without the DEV documents).
"""
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


def _stage_b_key(served_model: str) -> str:
    """RR-4: the weights pin is keyed on the SERVED model, not on the arm."""
    from tools.vlm_vast import MODELS

    for key, model in MODELS.items():
        if key != "a" and model["served"] == served_model:
            return key
    raise Refused("stage_b_model_unknown")


def _weights_bindings(receipts_dir: Path, keys: tuple[str, ...]) -> dict:
    """MAJOR-7 / RR-4: bind the latest successful fetch receipt per served model (path + sha256 + the
    recorded hashes); a model without a fetch receipt refuses — the pin is never silently empty."""
    out: dict = {}
    for key in keys:
        candidates = sorted(p for p in Path(receipts_dir).glob(f"fetch-{key}-*.json") if "FAILED" not in p.name)
        if not candidates:
            raise Refused("weights_receipt_missing")
        latest = candidates[-1]
        data = json.loads(latest.read_text(encoding="utf-8"))
        out[key] = {"receipt": bound(latest), "repo": data.get("repo"), "local_dir": data.get("local_dir"),
                    "hashes": [h for h in data.get("hashes", []) if h and " " in h]}
    return out


def _run(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    members = partitions.load_private_manifest(manifest_path)
    scope = partitions.manifest_scope(manifest_path)
    archive_root = Path(json.loads(manifest_path.read_text(encoding="utf-8"))["archive_root"])
    runtime_dir = Path(args.runtime_dir)
    token = _worker_token(runtime_dir)
    identity_client = StageAWorkerClient(args.stage_a_url, token=token) if args.arm != "reader_baseline" else None
    stage_a = identity_client if args.arm in ("stage_a_rules", "hybrid") else None
    stage_b = VlmClient(args.stage_b_url) if args.arm in ("stage_b_only", "hybrid") else None
    truth = ReaderTruth(Path(args.truth_cache), partitions.DEFAULT_RUN_OF_RECORD) if args.truth else None
    ctx = RunContext(arm=args.arm, stage_a=stage_a, stage_b=stage_b, stage_b_model=args.stage_b_model, truth=truth,
                     long_edge=args.long_edge, quality=args.jpeg_quality, seed=0, data_scope=scope,
                     hourly_rate=args.hourly_rate, concurrency=args.concurrency, identity_client=identity_client)
    weight_keys: tuple[str, ...] = ()
    if stage_a is not None:
        weight_keys += ("a",)
    if stage_b is not None:
        weight_keys += (_stage_b_key(args.stage_b_model),)
    weights = _weights_bindings(Path(args.receipts_dir), weight_keys) if weight_keys else {}
    try:
        result = run_wave(members, ctx, Path(args.out), archive_root=archive_root, manifest_binding=bound(manifest_path),
                          manifest_scope=scope, limit=args.limit, authorize=default_authorize,
                          resume_from=Path(args.resume_from) if args.resume_from else None, weights=weights)
    finally:
        if truth is not None:
            truth.close()
    print(json.dumps({"status": result["status"], "counts": result["counts"], "wave_wall_hours": result["wave_wall_hours"]}))
    return 0 if result["status"] == "complete" else 3


def _with_summary_block(page):
    """The synthetic ledger page plus the printed anchors a real statement carries: beginning and ending
    balances, the period, and the bank's own totals/counts. Arithmetic derives from the ledger itself."""
    from tests.paddle_synthetic import LEFT_MARGIN, LINE_HEIGHT, STARTING_BALANCE, SYNTHETIC_YEAR, SyntheticLine, SyntheticPage, _word

    rows = sum(1 for line in page.lines if line.words and line.words[0].text.startswith(f"{SYNTHETIC_YEAR}-"))
    total = sum(10 * i for i in range(1, rows + 1))
    y = max(word.y1 for line in page.lines for word in line.words) + 2 * LINE_HEIGHT
    extra = []
    for tokens in (
        (("STATEMENT", LEFT_MARGIN), ("PERIOD", LEFT_MARGIN + 70), (f"{SYNTHETIC_YEAR}-01-01", LEFT_MARGIN + 130), ("TO", LEFT_MARGIN + 210), (f"{SYNTHETIC_YEAR}-01-31", LEFT_MARGIN + 235)),
        (("BEGINNING", LEFT_MARGIN), ("BALANCE", LEFT_MARGIN + 70), (f"{STARTING_BALANCE:.2f}", LEFT_MARGIN + 330)),
        (("TOTAL", LEFT_MARGIN), ("DEPOSITS", LEFT_MARGIN + 45), (f"({rows})", LEFT_MARGIN + 115), (f"{total:.2f}", LEFT_MARGIN + 330)),
        (("TOTAL", LEFT_MARGIN), ("WITHDRAWALS", LEFT_MARGIN + 45), ("(0)", LEFT_MARGIN + 130), ("0.00", LEFT_MARGIN + 330)),
        (("ENDING", LEFT_MARGIN), ("BALANCE", LEFT_MARGIN + 55), (f"{STARTING_BALANCE + total:.2f}", LEFT_MARGIN + 330)),
    ):
        extra.append(SyntheticLine(words=tuple(_word(text, x, y) for text, x in tokens)))
        y += LINE_HEIGHT
    return SyntheticPage(width_pt=page.width_pt, height_pt=max(page.height_pt, y + 72.0), lines=page.lines + tuple(extra))


def _preflight(args: argparse.Namespace) -> int:
    """Synthetic pages only (no customer bytes): every model arm, one wave each, under the synthetic scope."""
    import hashlib
    from datetime import datetime, timezone

    from tests.paddle_synthetic import build_ledger_page, render_image_pdf, render_native_pdf, rotate_page_90
    from vlm.receipts import dump_new

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(args.out) / f"preflight-{stamp}"
    archive = root / "synthetic-archive"
    archive.mkdir(parents=True)
    page = build_ledger_page(n_rows=8)
    anchored = _with_summary_block(page)
    # anchored pages must be admitted strictly; the unanchored page is the refusal control (anchors_underdetermined)
    docs = {"native_anchored": render_native_pdf(anchored), "image_anchored": render_image_pdf(anchored, dpi=200),
            "native_unanchored": render_native_pdf(page), "rotated": render_native_pdf(rotate_page_90(anchored))}
    members = []
    for name, raw in docs.items():
        (archive / f"{name}.pdf").write_bytes(raw)
        members.append({"sha": hashlib.sha256(raw).hexdigest().upper(), "relative_path": f"{name}.pdf", "byte_size": len(raw),
                        "page_count": 1, "folder_label": "synthetic", "classification": "digital", "outcome_class": "synthetic",
                        "account_count": 1})
    manifest = root / "SYNTH.manifest.private.json"
    dump_new(manifest, {"manifest_version": 1, "name": "SYNTH", "data_scope": partitions.SYNTHETIC_SCOPE, "set_sha256": "synthetic",
                        "archive_root": str(archive), "members": members})
    codes = {}
    for arm in [a for a in ARMS if a != "reader_baseline"]:
        argv = ["run", "--arm", arm, "--manifest", str(manifest), "--out", str(root / arm),
                "--stage-a-url", args.stage_a_url, "--stage-b-url", args.stage_b_url, "--stage-b-model", args.stage_b_model,
                "--runtime-dir", args.runtime_dir, "--receipts-dir", args.receipts_dir]
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
    f.add_argument("--receipts-dir", default=str(DEFAULT_OUT))
    r = sub.add_parser("run")
    r.add_argument("--arm", choices=ARMS, required=True)
    r.add_argument("--manifest", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--limit", type=int, default=None)
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
    r.add_argument("--receipts-dir", default=str(DEFAULT_OUT))
    r.add_argument("--concurrency", type=int, default=1, help="Stage B pages in flight per document (server --max-num-seqs bound)")
    q = sub.add_parser("report")
    q.add_argument("--wave", required=True)
    q.add_argument("--exclude-manifest", default=None, help="private manifest whose members are reported as an excluded slice")
    g = sub.add_parser("regate", help="re-gate a completed wave's proposals under the current gate (no model calls)")
    g.add_argument("--wave", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--also", action="append", default=[], help="a wave that resumed --wave (disjoint documents); repeatable")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "regate":
            from vlm.regate import regate_wave

            result = regate_wave(Path(args.wave), Path(args.out), also=[Path(p) for p in args.also])
            print(json.dumps({"status": result["status"], "counts": result["counts"], "gate_version": result["gate_version"]}))
            return 0
        if args.command == "partitions":
            summary = partitions.write_manifests(Path(args.out))
            print(json.dumps({name: {"documents": s["documents"], "pages": s["pages"]} for name, s in summary.items()}))
            return 0
        if args.command == "preflight":
            return _preflight(args)
        if args.command == "run":
            return _run(args)
        if args.command == "report":
            exclude = frozenset(m.sha for m in partitions.load_private_manifest(Path(args.exclude_manifest))) if args.exclude_manifest else frozenset()
            path = report.write_report(Path(args.wave), exclude_shas=exclude)
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
