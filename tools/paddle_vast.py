"""tools/paddle_vast.py — the Paddle Vast.ai lifecycle tool (Phase 2.1 cell P,
`docs/agent-handoffs/P21-PADDLE.md` §5, §6).

Subcommands: `check`, `deploy`, `start`, `tunnel-up`, `tunnel-down`, `status`,
`stop`, `measure`. Every subprocess argument that contains the host, port or
user is built from `ocr.paddle_config.PaddleSettings`, never a literal in
this file; every printed line is masked through `mask_text` before it
reaches stdout, so the connection information the process environment holds
never appears in this tool's own output (`tests/test_paddle_vast_tool.py`
scans for the placeholder host `tests/test_paddle_config.py` uses to prove
this). `measure` refuses any fixture path under `Bank Statements/`,
`tests/corpus_cache/` or `discovery_reports/` (D8, M12) — it only ever reads
`tests/paddle_synthetic.py`'s generated pages.

Every network-touching function takes an injectable `runner` / `popen`
callable (a `subprocess.run` / `subprocess.Popen`-shaped seam) so
`tests/test_paddle_vast_tool.py` proves argument construction and masking
without ever opening a socket or an SSH connection.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import secrets
import socket
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from ocr.paddle_client import PaddleClient, PaddleTransportError, PaddleWorkerStatus, probe as client_probe, verify_identity
from ocr.paddle_config import (
    DATA_SCOPE_SYNTHETIC,
    PADDLE_RASTER_DPI,
    PaddleConfigError,
    PaddleRefused,
    PaddleSettings,
    check_remote_authorization,
    load_paddle_settings,
    paddle_runtime_identity,
)
from ocr.rasterize import rasterize_pdf

__all__ = [
    "FORBIDDEN_FIXTURE_SUBSTRINGS",
    "HOST_PLACEHOLDER",
    "PaddleVastError",
    "USER_PLACEHOLDER",
    "cmd_check",
    "cmd_deploy",
    "cmd_measure",
    "cmd_start",
    "cmd_status",
    "cmd_stop",
    "cmd_tunnel_down",
    "cmd_tunnel_up",
    "mask_text",
    "main",
]

HOST_PLACEHOLDER = "<HOST>"
USER_PLACEHOLDER = "<USER>"
TOKEN_PLACEHOLDER = "<TOKEN>"

REMOTE_WORKER_DIR = "/workspace/ci_paddle"
REMOTE_WORKER_PATH = f"{REMOTE_WORKER_DIR}/paddle_worker.py"
REMOTE_PID_PATH = f"{REMOTE_WORKER_DIR}/worker.pid"
REMOTE_LOG_PATH = f"{REMOTE_WORKER_DIR}/worker.log"

#: D8 / M12: `measure` refuses any fixture path naming a real-data location,
#: by substring — this is deliberately broader than a prefix match so a
#: relative or absolute path pointing INTO one of these directories from
#: anywhere is caught.
FORBIDDEN_FIXTURE_SUBSTRINGS = ("Bank Statements", "tests/corpus_cache", "tests\\corpus_cache", "discovery_reports")


class PaddleVastError(RuntimeError):
    """A lifecycle-tool-level refusal (a forbidden fixture path, a tunnel
    port already in use, a missing pidfile). Never carries a connection
    value."""


def mask_text(text: str, settings: PaddleSettings) -> str:
    """The ONLY way this tool's output reaches a caller: every occurrence of
    the real host/user (and any worker token this process knows about) is
    replaced by a placeholder. Applied to every string this module returns
    or prints."""
    masked = text
    if settings.vast_host:
        masked = masked.replace(settings.vast_host, HOST_PLACEHOLDER)
    if settings.vast_ssh_user:
        masked = masked.replace(settings.vast_ssh_user, USER_PLACEHOLDER)
    if settings.worker_token:
        masked = masked.replace(settings.worker_token, TOKEN_PLACEHOLDER)
    return masked


def _mask_json(payload: dict, settings: PaddleSettings) -> dict:
    return json.loads(mask_text(json.dumps(payload), settings))


def _ssh_command(settings: PaddleSettings, remote_command: str) -> list[str]:
    return [
        "ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
        "-p", str(settings.vast_ssh_port), f"{settings.vast_ssh_user}@{settings.vast_host}",
        remote_command,
    ]


def _scp_command(settings: PaddleSettings, local_path: str, remote_path: str) -> list[str]:
    return [
        "scp", "-o", "BatchMode=yes", "-P", str(settings.vast_ssh_port),
        local_path, f"{settings.vast_ssh_user}@{settings.vast_host}:{remote_path}",
    ]


def _tunnel_command(settings: PaddleSettings) -> list[str]:
    return [
        "ssh", "-N", "-o", "ExitOnForwardFailure=yes", "-o", "BatchMode=yes",
        "-L", f"127.0.0.1:{settings.tunnel_local_port}:127.0.0.1:{settings.worker_port}",
        "-p", str(settings.vast_ssh_port), f"{settings.vast_ssh_user}@{settings.vast_host}",
    ]


def _env_prefix(settings: PaddleSettings, token: str | None) -> str:
    parts = [f"PADDLE_PROVIDER={settings.provider}", f"PADDLE_EXECUTION_CLASS={settings.execution_class}",
             f"PADDLE_WORKER_PORT={settings.worker_port}"]
    if token:
        parts.append(f"PADDLE_WORKER_TOKEN={token}")
    return " ".join(parts)


def _runtime_dir(settings: PaddleSettings) -> Path:
    path = Path(settings.runtime_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _port_listening(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, timeout=10,
        )
        return str(pid) in completed.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _terminate_pid(pid: int) -> None:
    import signal

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

def cmd_check(settings: PaddleSettings, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    """Env presence (names only), `nvidia-smi` over SSH, and the remote
    `/venv/main` package versions compared against the D5 pins. Nothing here
    starts or stops anything."""
    result: dict[str, Any] = {
        "env_present": {
            name: bool(os.environ.get(name))
            for name in ("PADDLE_PROVIDER", "PADDLE_EXECUTION_CLASS", "PADDLE_VAST_HOST",
                        "PADDLE_VAST_SSH_PORT", "PADDLE_VAST_SSH_USER")
        },
        "provider": settings.provider,
        "execution_class": settings.execution_class,
    }
    if settings.provider != "vast.ai":
        return result

    gpu_proc = runner(
        _ssh_command(settings, "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader"),
        capture_output=True, text=True, timeout=30,
    )
    result["gpu"] = gpu_proc.stdout.strip() if gpu_proc.returncode == 0 else None

    version_cmd = (
        "source /venv/main/bin/activate >/dev/null 2>&1; "
        "python -c \"import paddleocr, paddle; print(paddleocr.__version__); print(paddle.__version__)\""
    )
    version_proc = runner(_ssh_command(settings, version_cmd), capture_output=True, text=True, timeout=60)
    lines = [line for line in version_proc.stdout.strip().splitlines() if line]
    remote_paddleocr = lines[-2] if len(lines) >= 2 else None
    remote_paddlepaddle = lines[-1] if len(lines) >= 1 else None
    result["remote_paddleocr_version"] = remote_paddleocr
    result["remote_paddlepaddle_version"] = remote_paddlepaddle

    pins = paddle_runtime_identity()
    result["versions_match_pins"] = (
        remote_paddleocr == pins["paddleocr_version"] and remote_paddlepaddle == pins["paddlepaddle_version"]
    )
    return _mask_json(result, settings)


# ---------------------------------------------------------------------------
# deploy
# ---------------------------------------------------------------------------

def cmd_deploy(settings: PaddleSettings, *, runner: Callable[..., Any] = subprocess.run,
               local_worker_path: str | None = None) -> dict:
    """`scp ocr/paddle_worker.py` to the remote host, then run
    `--self-check` there. Copies ONLY that one file — nothing else from the
    repository goes remote."""
    local_path = local_worker_path or str(
        Path(__file__).resolve().parent.parent / "ocr" / "paddle_worker.py"
    )
    mkdir_proc = runner(_ssh_command(settings, f"mkdir -p {REMOTE_WORKER_DIR}"),
                         capture_output=True, text=True, timeout=30)
    scp_proc = runner(_scp_command(settings, local_path, REMOTE_WORKER_PATH),
                       capture_output=True, text=True, timeout=60)
    self_check_cmd = (
        f"{_env_prefix(settings, token=None)} /venv/main/bin/python {REMOTE_WORKER_PATH} --self-check"
    )
    check_proc = runner(_ssh_command(settings, self_check_cmd), capture_output=True, text=True, timeout=60)
    result: dict[str, Any] = {
        "mkdir_ok": mkdir_proc.returncode == 0,
        "scp_ok": scp_proc.returncode == 0,
        "self_check_ok": check_proc.returncode == 0,
    }
    if check_proc.returncode == 0:
        try:
            result["identity"] = json.loads(check_proc.stdout)
        except json.JSONDecodeError:
            result["identity"] = None
    return _mask_json(result, settings)


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------

def cmd_start(settings: PaddleSettings, *, runner: Callable[..., Any] = subprocess.run,
              token: str | None = None) -> dict:
    """Launch the worker on the remote host under `nohup`, detached. A
    session token is generated (`secrets.token_urlsafe`) unless one is
    supplied, written to the gitignored runtime dir, and exported into the
    remote command line — never printed."""
    token = token or secrets.token_urlsafe(32)
    token_path = _runtime_dir(settings) / "worker.token"
    token_path.write_text(token, encoding="utf-8")
    try:
        token_path.chmod(0o600)
    except OSError:  # pragma: no cover - best effort on platforms without POSIX modes
        pass

    remote_cmd = (
        "source /venv/main/bin/activate >/dev/null 2>&1; "
        f"nohup env {_env_prefix(settings, token)} /venv/main/bin/python {REMOTE_WORKER_PATH} "
        f"> {REMOTE_LOG_PATH} 2>&1 < /dev/null & echo $! > {REMOTE_PID_PATH}"
    )
    proc = runner(_ssh_command(settings, remote_cmd), capture_output=True, text=True, timeout=30)
    return _mask_json({"started": proc.returncode == 0, "worker_port": settings.worker_port}, settings)


def cmd_stop(settings: PaddleSettings, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    """Stop the REMOTE worker process (from its own pidfile). Does not touch
    the local SSH tunnel — see `cmd_tunnel_down`."""
    remote_cmd = (
        f"if [ -f {REMOTE_PID_PATH} ]; then kill $(cat {REMOTE_PID_PATH}) 2>/dev/null; "
        f"rm -f {REMOTE_PID_PATH}; echo stopped; else echo not_running; fi"
    )
    proc = runner(_ssh_command(settings, remote_cmd), capture_output=True, text=True, timeout=30)
    return _mask_json({"remote_output": proc.stdout.strip()}, settings)


# ---------------------------------------------------------------------------
# tunnel-up / tunnel-down
# ---------------------------------------------------------------------------

def cmd_tunnel_up(settings: PaddleSettings, *, popen: Callable[..., Any] = subprocess.Popen) -> dict:
    """Open the SSH tunnel as a detached process, pid recorded in the
    runtime dir. Refuses if the local port is already listening (never a
    second tunnel stacked on the first)."""
    if _port_listening(settings.tunnel_local_port):
        raise PaddleVastError(
            f"local port {settings.tunnel_local_port} is already listening; refusing a second tunnel"
        )
    process = popen(_tunnel_command(settings), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (_runtime_dir(settings) / "tunnel.pid").write_text(str(process.pid), encoding="utf-8")
    return {"pid": process.pid, "local_port": settings.tunnel_local_port}


def cmd_tunnel_down(settings: PaddleSettings) -> dict:
    pid_path = _runtime_dir(settings) / "tunnel.pid"
    if not pid_path.exists():
        return {"stopped": False, "reason": "no tunnel.pid"}
    pid = int(pid_path.read_text(encoding="utf-8").strip())
    _terminate_pid(pid)
    pid_path.unlink(missing_ok=True)
    return {"stopped": True, "pid": pid}


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def cmd_status(settings: PaddleSettings, *, client: PaddleClient | None = None) -> dict:
    status: PaddleWorkerStatus = client_probe(settings, client=client)
    tunnel_pid_path = _runtime_dir(settings) / "tunnel.pid"
    tunnel_running = False
    if tunnel_pid_path.exists():
        try:
            tunnel_running = _pid_alive(int(tunnel_pid_path.read_text(encoding="utf-8").strip()))
        except (ValueError, OSError):
            tunnel_running = False
    return {
        "settings": settings.masked(),
        "probe": {"available": status.available, "reason": status.reason, "error_type": status.error_type},
        "tunnel_running": tunnel_running,
    }


# ---------------------------------------------------------------------------
# measure (D8, §6)
# ---------------------------------------------------------------------------

def _refuse_forbidden_fixture(path: str | None) -> None:
    if path is None:
        return
    normalized = path.replace("\\", "/")
    for forbidden in FORBIDDEN_FIXTURE_SUBSTRINGS:
        if forbidden.replace("\\", "/") in normalized:
            raise PaddleVastError(f"measure refuses a fixture path under {forbidden!r}: {path!r}")


def cmd_measure(
    settings: PaddleSettings,
    *,
    client: PaddleClient | None = None,
    fixture_path: str | None = None,
    n_rows: int = 8,
    warm_requests: int = 20,
    dpi: int = PADDLE_RASTER_DPI,
    hourly_rate: float | None = None,
    gpu_sampler: Callable[[], dict | None] | None = None,
) -> dict:
    """The runtime/cost measurement, on a synthetic fixture ONLY (D8, M12).
    `fixture_path` — if a caller passes one — must not name a real-data
    location; the default is `tests.paddle_synthetic.build_ledger_page`,
    which never touches disk at all.
    """
    _refuse_forbidden_fixture(fixture_path)

    from tests.paddle_synthetic import build_ledger_page, render_image_pdf

    check_remote_authorization(settings, DATA_SCOPE_SYNTHETIC)
    client = client or PaddleClient(settings)
    identity = verify_identity(settings, client=client)

    page = build_ledger_page(n_rows=n_rows)
    pdf_bytes = render_image_pdf(page, dpi=dpi)
    image = rasterize_pdf(pdf_bytes, dpi=dpi)[0]
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    started_at = time.time()
    cold: dict[str, Any] | None = None
    warm_latencies_ms: list[float] = []
    bytes_sent = len(png_bytes)
    bytes_received = 0
    for index in range(warm_requests + 1):
        t0 = time.perf_counter()
        response = client.ocr_page(png_bytes, page_index=0, request_id=f"measure-{index}")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        bytes_received = max(bytes_received, len(json.dumps(response)))
        timing = response.get("timing") or {}
        if index == 0:
            cold = {"end_to_end_ms": elapsed_ms, "inference_ms": timing.get("inference_ms")}
        else:
            warm_latencies_ms.append(elapsed_ms)
    finished_at = time.time()

    sorted_latencies = sorted(warm_latencies_ms)
    p95_index = max(0, int(len(sorted_latencies) * 0.95) - 1) if sorted_latencies else None
    warm = {
        "median_end_to_end_ms": statistics.median(warm_latencies_ms) if warm_latencies_ms else None,
        "p95_end_to_end_ms": sorted_latencies[p95_index] if p95_index is not None else None,
        "n": len(warm_latencies_ms),
    }

    gpu_sample = gpu_sampler() if gpu_sampler else None
    runtime_seconds = finished_at - started_at
    cost = (runtime_seconds / 3600.0) * hourly_rate if hourly_rate else None

    report = {
        "identity": identity,
        "fixture": {"n_rows": n_rows, "dpi": dpi, "width": image.width, "height": image.height},
        "cold": cold,
        "warm": warm,
        "bytes_sent_per_page": bytes_sent,
        "bytes_received_per_page": bytes_received,
        "gpu": gpu_sample,
        "measurement_wall_seconds": runtime_seconds,
        "hourly_rate": hourly_rate,
        "cost": cost if cost is not None else "rate not measured",
    }
    masked = _mask_json(report, settings)

    runtime_dir = _runtime_dir(settings)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    (runtime_dir / f"measure-{stamp}.json").write_text(json.dumps(masked, indent=2), encoding="utf-8")
    return masked


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paddle_vast")
    parser.add_argument(
        "command",
        choices=("check", "deploy", "start", "tunnel-up", "tunnel-down", "status", "stop", "measure"),
    )
    parser.add_argument("--hourly-rate", type=float, default=None)
    parser.add_argument("--n-rows", type=int, default=8)
    parser.add_argument("--warm-requests", type=int, default=20)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        settings = load_paddle_settings()
    except PaddleConfigError as exc:
        print(json.dumps({"error": "paddle_config_missing", "detail": str(exc)}))
        return 2

    try:
        if args.command == "check":
            print(json.dumps(cmd_check(settings), indent=2))
        elif args.command == "deploy":
            print(json.dumps(cmd_deploy(settings), indent=2))
        elif args.command == "start":
            print(json.dumps(cmd_start(settings), indent=2))
        elif args.command == "tunnel-up":
            print(json.dumps(cmd_tunnel_up(settings), indent=2))
        elif args.command == "tunnel-down":
            print(json.dumps(cmd_tunnel_down(settings), indent=2))
        elif args.command == "status":
            print(json.dumps(cmd_status(settings), indent=2))
        elif args.command == "stop":
            print(json.dumps(cmd_stop(settings), indent=2))
        elif args.command == "measure":
            print(json.dumps(cmd_measure(
                settings, n_rows=args.n_rows, warm_requests=args.warm_requests, hourly_rate=args.hourly_rate,
            ), indent=2))
    except (PaddleVastError, PaddleRefused, PaddleTransportError) as exc:
        print(mask_text(json.dumps({"error": type(exc).__name__, "detail": str(exc)}), settings))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
