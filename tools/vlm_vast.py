"""Lifecycle of the ceiling-experiment servers on the rented host. Everything printed is masked.

Reuses the reviewed transport of `tools/paddle_vast.py`; adds nothing to the trust boundary: SSH to the
configured host, loopback-only servers, one tunnel with four forwards.

Review closures: MAJOR-10 (b9 has its own port and is part of stop/status), BLOCK-2 (the worker is started
with the local declaration exported so its /version can echo it), MINOR (the worker token is masked in
every printed value like the host, user and Paddle token).
"""
from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ocr.paddle_config import PaddleConfigError, load_paddle_settings
from tools.paddle_vast import (PaddleVastError, _pid_alive, _popen, _port_listening, _run, _runtime_dir, _scp_command,
                               _ssh_command, _terminate_pid, mask_text)

REMOTE_DIR = "/workspace/ci_vlm"
MODELS_DIR = "/workspace/models"
HF_HOME = "/workspace/.hf_home"
PADDLE_PYTHON = "/workspace/paddleocr-env/bin/python"
HF_PYTHON = "/venv/main/bin/python"
PORTS = {"a": 18001, "b": 18002, "worker": 18003, "b9": 18004}
SERVER_KEYS = ("a", "b", "b9", "worker")
MODELS = {
    "a": {"repo": "PaddlePaddle/PaddleOCR-VL-1.6", "served": "PaddleOCR-VL-1.6-0.9B", "size_gb": 2.0},
    "b": {"repo": "Qwen/Qwen3.5-4B", "served": "Qwen/Qwen3.5-4B", "size_gb": 9.4},
    "b9": {"repo": "RedHatAI/Qwen3.5-9B-FP8-dynamic", "served": "RedHatAI/Qwen3.5-9B-FP8-dynamic", "size_gb": 14.1},
}
SERVE_FLAGS = {
    "a": "--trust-remote-code --max-num-batched-tokens 8192 --no-enable-prefix-caching --mm-processor-cache-gb 0 "
         "--gpu-memory-utilization 0.28 --max-model-len 8192 --max-num-seqs 4",
    "b": "--max-model-len 16384 --max-num-seqs 4 --max-num-batched-tokens 4096 --gpu-memory-utilization 0.55 "
         "--limit-mm-per-prompt.image 1 --structured-outputs-config.backend xgrammar",
    "b9": "--max-model-len 16384 --max-num-seqs 4 --max-num-batched-tokens 4096 --gpu-memory-utilization 0.62 "
          "--limit-mm-per-prompt.image 1 --structured-outputs-config.backend xgrammar",
}
COMMON_ENV = f"HF_HOME={HF_HOME} HF_HUB_OFFLINE=1 VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1"
DISK_MARGIN_GB = 2.0
RECEIPTS = Path("discovery_reports/train13-logs/p3ceiling")
TOKEN_PLACEHOLDER = "<VLM-TOKEN>"


def _local_dir(key: str) -> str:
    return f"{MODELS_DIR}/{MODELS[key]['repo'].replace('/', '__')}"


def serve_command(key: str) -> str:
    model = MODELS[key]
    return (f"vllm serve {_local_dir(key)} --served-model-name {model['served']} --host 127.0.0.1 --port {PORTS[key]} "
            f"--download-dir {MODELS_DIR} {SERVE_FLAGS[key]}")


def tunnel_command(settings) -> list[str]:
    cmd = ["ssh", "-N", "-o", "ExitOnForwardFailure=yes", "-o", "BatchMode=yes"]
    for key in SERVER_KEYS:
        port = PORTS[key]
        cmd += ["-L", f"127.0.0.1:{port}:127.0.0.1:{port}"]
    cmd += ["-p", str(settings.vast_ssh_port), f"{settings.vast_ssh_user}@{settings.vast_host}"]
    return cmd


def _token_path(settings) -> Path:
    return _runtime_dir(settings) / "vlm_worker.token"


def _token(settings) -> str:
    path = _token_path(settings)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    path.write_text(token, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return token


def _mask(text: str, settings) -> str:
    masked = mask_text(text or "", settings)
    path = _token_path(settings)
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            masked = masked.replace(token, TOKEN_PLACEHOLDER)
    return masked


def _ssh(settings, runner, command: str, timeout: float = 120.0):
    return _run(runner, _ssh_command(settings, command), capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout)


def _disk_free_gb(settings, runner) -> float:
    proc = _ssh(settings, runner, "df -BG --output=avail / | tail -1 | tr -dc '0-9'")
    digits = "".join(ch for ch in (proc.stdout or "") if ch.isdigit())
    return float(digits or 0)


def cmd_check(settings, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    gpu = _ssh(settings, runner, "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader").stdout or ""
    versions = _ssh(settings, runner, "python3 -m pip list 2>/dev/null | grep -i -E '^(vllm|torch|transformers|xgrammar) ' ; "
                                      f"{PADDLE_PYTHON} -m pip list 2>/dev/null | grep -i -E '^(paddleocr|paddlex|paddlepaddle-gpu|pypdfium2) '").stdout or ""
    ports = (_ssh(settings, runner, "ss -ltn 2>/dev/null | grep -o -E '127.0.0.1:(18001|18002|18003|18004)' | sort -u").stdout or "").split()
    return {"provider": settings.provider, "execution_class": settings.execution_class, "gpu": _mask(gpu.strip(), settings),
            "disk_free_gb": _disk_free_gb(settings, runner), "versions": _mask(versions, settings).split("\n"),
            "listening": [p.split(":")[-1] for p in ports]}


def cmd_fetch(settings, key: str, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    model = MODELS[key]
    free = _disk_free_gb(settings, runner)
    if free < model["size_gb"] + DISK_MARGIN_GB:
        raise PaddleVastError(f"disk_insufficient:{free:.0f}GB_free")
    target = _local_dir(key)
    snippet = ("from huggingface_hub import snapshot_download as d; import sys; "
               f"print(d(repo_id=sys.argv[1], local_dir=sys.argv[2]))")
    fetch = (f"mkdir -p {MODELS_DIR} && HF_HOME={HF_HOME} HF_HUB_DISABLE_TELEMETRY=1 {HF_PYTHON} -c \"{snippet}\" "
             f"{model['repo']} {target} > {REMOTE_DIR}/fetch-{key}.log 2>&1; echo EXIT=$?")
    proc = _ssh(settings, runner, f"mkdir -p {REMOTE_DIR} && {fetch}", timeout=3600.0)
    exit_code = (proc.stdout or "").strip().split("EXIT=")[-1].strip()
    hashes = _ssh(settings, runner, f"cd {target} && sha256sum config.json *.safetensors 2>/dev/null; "
                                    f"cat .cache/huggingface/download/*.metadata 2>/dev/null | head -c 2000", timeout=600.0).stdout or ""
    receipt = {"key": key, "repo": model["repo"], "local_dir": target,
               "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "exit": exit_code, "hashes": _mask(hashes, settings).split("\n"),
               "disk_free_gb_before": free, "disk_free_gb_after": _disk_free_gb(settings, runner)}
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if exit_code != "0":
        failed = RECEIPTS / f"fetch-{key}-FAILED-{stamp}.json"
        failed.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        raise PaddleVastError(f"fetch_failed:exit_{exit_code}")
    path = RECEIPTS / f"fetch-{key}-{stamp}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {**receipt, "receipt": str(path)}


def cmd_deploy(settings, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    _ssh(settings, runner, f"mkdir -p {REMOTE_DIR}")
    local = Path("vlm/stage_a_worker.py")
    _run(runner, _scp_command(settings, str(local), f"{REMOTE_DIR}/stage_a_worker.py"), capture_output=True, text=True, timeout=120)
    check = _ssh(settings, runner, f"{PADDLE_PYTHON} {REMOTE_DIR}/stage_a_worker.py --self-check")
    return {"deployed": True, "self_check": _mask((check.stdout or "").strip(), settings)}


def cmd_start(settings, key: str, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    if key == "worker":
        env = (f"VLM_A_WORKER_TOKEN={_token(settings)} VLM_A_BACKEND=vllm-server "
               f"VLM_A_SERVER_URL=http://127.0.0.1:{PORTS['a']}/v1 VLM_A_WORKER_PORT={PORTS['worker']} "
               f"PADDLE_PROVIDER={settings.provider} PADDLE_EXECUTION_CLASS={settings.execution_class}")
        launch = f"{PADDLE_PYTHON} {REMOTE_DIR}/stage_a_worker.py"
    else:
        env = COMMON_ENV
        launch = serve_command(key)
    # The launch runs inside a subshell that exits right after recording the pid, so the SSH session
    # gets EOF immediately; the server's own descriptors point at the log file and /dev/null.
    remote = (f"mkdir -p {REMOTE_DIR}; cd {REMOTE_DIR}; "
              f"( nohup env {env} {launch} > {REMOTE_DIR}/{key}.log 2>&1 < /dev/null & echo $! > {REMOTE_DIR}/{key}.pid ); "
              f"cat {REMOTE_DIR}/{key}.pid")
    proc = _ssh(settings, runner, remote, timeout=60.0)
    return {"started": key, "remote_pid": _mask((proc.stdout or "").strip(), settings), "port": PORTS[key]}


def cmd_stop(settings, key: str, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    keys = ("worker", "b9", "b", "a") if key == "all" else (key,)
    out = {}
    for k in keys:
        proc = _ssh(settings, runner, f"if [ -f {REMOTE_DIR}/{k}.pid ]; then kill $(cat {REMOTE_DIR}/{k}.pid) 2>/dev/null; sleep 3; "
                                      f"kill -9 $(cat {REMOTE_DIR}/{k}.pid) 2>/dev/null; rm -f {REMOTE_DIR}/{k}.pid; echo stopped; else echo absent; fi")
        out[k] = _mask((proc.stdout or "").strip(), settings)
    return out


def cmd_status(settings, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    proc = _ssh(settings, runner,
                f"for k in a b b9 worker; do if [ -f {REMOTE_DIR}/$k.pid ] && kill -0 $(cat {REMOTE_DIR}/$k.pid) 2>/dev/null; "
                "then echo $k=alive; else echo $k=down; fi; done; "
                "ss -ltn 2>/dev/null | grep -o -E '127.0.0.1:(18001|18002|18003|18004)' | sort -u; "
                "nvidia-smi --query-gpu=memory.used --format=csv,noheader")
    return {"remote": _mask(proc.stdout or "", settings).split("\n"),
            "tunnel_local_ports_listening": {str(PORTS[k]): _port_listening(PORTS[k]) for k in SERVER_KEYS}}


def cmd_tunnel_up(settings, *, popen: Callable[..., Any] = subprocess.Popen) -> dict:
    for key in SERVER_KEYS:
        if _port_listening(PORTS[key]):
            raise PaddleVastError(f"local_port_in_use:{PORTS[key]}")
    process = _popen(popen, tunnel_command(settings), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pid_path = _runtime_dir(settings) / "vlm_tunnel.pid"
    pid_path.write_text(str(process.pid), encoding="utf-8")
    time.sleep(2.0)
    return {"pid": process.pid, "ports": [PORTS[k] for k in SERVER_KEYS]}


def cmd_tunnel_down(settings) -> dict:
    pid_path = _runtime_dir(settings) / "vlm_tunnel.pid"
    if not pid_path.exists():
        return {"stopped": False, "reason": "no vlm_tunnel.pid"}
    pid = int(pid_path.read_text(encoding="utf-8").strip() or 0)
    if pid and _pid_alive(pid):
        _terminate_pid(pid)
    pid_path.unlink()
    return {"stopped": True, "pid": pid}


_ATTEST = ("SERVER_PROCESSES=$(ps -eo cmd | grep -v grep | grep -c -E 'vllm serve|stage_a_worker.py'); "
           "NEW_FILES=$(find {dir} -type f -newermt '@{since}' ! -name '*.log' ! -name '*.pid' 2>/dev/null | wc -l); "
           "TMP_IMAGES=$(find /tmp -type f -newermt '@{since}' \\( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \\) 2>/dev/null | wc -l); "
           "echo SERVER_PROCESSES=$SERVER_PROCESSES; echo NEW_FILES=$NEW_FILES; echo TMP_IMAGES=$TMP_IMAGES")


def cmd_attest(settings, *, runner: Callable[..., Any] = subprocess.run, since_epoch: float) -> dict:
    proc = _ssh(settings, runner, _ATTEST.format(dir=REMOTE_DIR, since=int(since_epoch)))
    counts: dict[str, int] = {}
    for line in (proc.stdout or "").splitlines():
        if "=" in line:
            name, value = line.split("=", 1)
            digits = "".join(ch for ch in value if ch.isdigit())
            counts[name.strip()] = int(digits or 0)
    inspected = set(counts) == {"SERVER_PROCESSES", "NEW_FILES", "TMP_IMAGES"}
    return {"inspected": inspected, "counts": counts, "passed": inspected and all(v == 0 for v in counts.values()),
            "retention_declared": "none", "provider": settings.provider, "execution_class": settings.execution_class,
            "attested_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vlm_vast")
    parser.add_argument("command", choices=("check", "fetch", "deploy", "start", "stop", "status", "tunnel-up",
                                            "tunnel-down", "attest"))
    parser.add_argument("--key", choices=("a", "b", "b9", "worker", "all"), default=None)
    parser.add_argument("--since-epoch", type=float, default=0.0)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        settings = load_paddle_settings()
    except PaddleConfigError as exc:
        print(json.dumps({"error": "paddle_config_missing", "detail": str(exc)}))
        return 2
    try:
        if args.command == "check":
            out = cmd_check(settings)
        elif args.command == "fetch":
            out = cmd_fetch(settings, args.key)
        elif args.command == "deploy":
            out = cmd_deploy(settings)
        elif args.command == "start":
            out = cmd_start(settings, args.key)
        elif args.command == "stop":
            out = cmd_stop(settings, args.key or "all")
        elif args.command == "status":
            out = cmd_status(settings)
        elif args.command == "tunnel-up":
            out = cmd_tunnel_up(settings)
        elif args.command == "tunnel-down":
            out = cmd_tunnel_down(settings)
        else:
            out = cmd_attest(settings, since_epoch=args.since_epoch)
    except PaddleVastError as exc:
        print(json.dumps({"error": _mask(str(exc), settings)}))
        return 1
    print(_mask(json.dumps(out, indent=2), settings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
