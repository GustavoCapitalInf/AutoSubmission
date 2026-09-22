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
import os
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
PADDLE_PYTHON = os.environ.get("VLM_WORKER_PYTHON") or "/workspace/paddleocr-env/bin/python"   # the worker builds its parser lazily
HF_PYTHON = "/venv/main/bin/python"
PORTS = {"a": 18001, "b": 18002, "worker": 18003, "b9": 18004, "b27": 18004, "b27ft": 18004, "b27lora": 18004}   # the 18004 keys run one at a time
SERVER_KEYS = ("a", "b", "b9", "worker")
MODELS = {
    "a": {"repo": "PaddlePaddle/PaddleOCR-VL-1.6", "served": "PaddleOCR-VL-1.6-0.9B", "size_gb": 2.0},
    "b": {"repo": "Qwen/Qwen3.5-4B", "served": "Qwen/Qwen3.5-4B", "size_gb": 9.4},
    "b9": {"repo": "RedHatAI/Qwen3.5-9B-FP8-dynamic", "served": "RedHatAI/Qwen3.5-9B-FP8-dynamic", "size_gb": 14.1},
    "b27": {"repo": "nvidia/Qwen3.8-27B-NVFP4", "served": "nvidia/Qwen3.8-27B-NVFP4", "size_gb": 22.0},
    # R17: the BF16 base for LoRA fine-tuning (fetched, never served as is) and the merged tuned model
    # (written by tools/vlm_train_lora.py merge on the host, served for evaluation through the same gate).
    "b27bf16": {"repo": "Qwen/Qwen3.8-27B", "served": "Qwen/Qwen3.8-27B", "size_gb": 57.0},
    "b27ft": {"repo": "local/Qwen3.8-27B-lora01", "served": "local/Qwen3.8-27B-lora01", "size_gb": 57.0},
    # R17 evaluation without merging: the BF16 base served with the adapter as a vLLM LoRA module; requests name
    # the module. The adapter path comes from VLM_LORA_ADAPTER (default: the run's final adapter).
    "b27lora": {"repo": "Qwen/Qwen3.8-27B", "served": "lora01", "size_gb": 57.0, "base": "b27bf16"},
}
LORA_ADAPTER_DEFAULT = "/workspace/lora-01/adapter-final"
SERVE_FLAGS = {
    "a": "--trust-remote-code --max-num-batched-tokens 8192 --no-enable-prefix-caching --mm-processor-cache-gb 0 "
         "--gpu-memory-utilization 0.28 --max-model-len 8192 --max-num-seqs 4",
    "b": "--max-model-len 32768 --max-num-seqs 4 --max-num-batched-tokens 4096 --gpu-memory-utilization 0.55 "
         "--limit-mm-per-prompt.image 1 --structured-outputs-config.backend xgrammar",
    "b9": "--max-model-len 16384 --max-num-seqs 4 --max-num-batched-tokens 4096 --gpu-memory-utilization 0.62 "
          "--limit-mm-per-prompt.image 1 --structured-outputs-config.backend xgrammar",
    # Single RTX 5090 (vLLM recipe for Qwen3.8-27B NVFP4 says CUDA graphs off to fit): eager ran at ~10 tok/s
    # per request with the GPU 19 percent busy (launch-bound hybrid layers), so graphs are captured for the
    # few batch sizes we use and the memory share is lowered to leave room for the capture. The layout
    # parser is stopped while this runs (Gustavo, 2026-09-18), so the share is the whole card.
    "b27": "--max-model-len 32768 --max-num-seqs 4 --max-num-batched-tokens 4096 --gpu-memory-utilization 0.85 "
           "--kv-cache-dtype fp8 --compilation-config '{\"cudagraph_capture_sizes\":[1,2,4]}' "
           "--limit-mm-per-prompt.image 1 --structured-outputs-config.backend xgrammar",
}
# Card profiles (VLM_GPU_PROFILE, default 32gb): the same model served with the batch the card can hold.
# 96gb = RTX PRO 6000 Blackwell (2026-09-18): the 20 GB of weights leave room for a cache that batches
# 16 pages per step; the card decodes a single page at the 5090's speed, the batch is the speedup.
SERVE_PROFILES = {
    "b27": {
        "32gb": SERVE_FLAGS["b27"],
        "96gb": "--max-model-len 32768 --max-num-seqs 16 --max-num-batched-tokens 8192 --gpu-memory-utilization 0.90 "
                "--kv-cache-dtype fp8 --compilation-config '{\"cudagraph_capture_sizes\":[1,2,4,8,16]}' "
                "--limit-mm-per-prompt.image 1 --structured-outputs-config.backend xgrammar",
    },
    "b27lora": {
        "96gb": "--max-model-len 32768 --max-num-seqs 8 --max-num-batched-tokens 8192 --gpu-memory-utilization 0.92 "
                "--kv-cache-dtype fp8 --compilation-config '{\"cudagraph_capture_sizes\":[1,2,4,8]}' "
                "--limit-mm-per-prompt.image 1 --structured-outputs-config.backend xgrammar --enable-lora --max-lora-rank 32",
    },
    # The merged BF16 model (56 GB of weights) leaves ~30 GB for the cache on the 96 GB card.
    "b27ft": {
        "96gb": "--max-model-len 32768 --max-num-seqs 8 --max-num-batched-tokens 8192 --gpu-memory-utilization 0.92 "
                "--kv-cache-dtype fp8 --compilation-config '{\"cudagraph_capture_sizes\":[1,2,4,8]}' "
                "--limit-mm-per-prompt.image 1 --structured-outputs-config.backend xgrammar",
    },
}
COMMON_ENV = f"HF_HOME={HF_HOME} HF_HUB_OFFLINE=1 VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1"
DISK_MARGIN_GB = 2.0
RECEIPTS = Path("discovery_reports/train13-logs/p3ceiling")
TOKEN_PLACEHOLDER = "<VLM-TOKEN>"


def _local_dir(key: str) -> str:
    return f"{MODELS_DIR}/{MODELS[key]['repo'].replace('/', '__')}"


def serve_flags(key: str, profile: str | None = None) -> str:
    """The serve flags for `key`; a key with card profiles takes VLM_GPU_PROFILE (default 32gb)."""
    profiles = SERVE_PROFILES.get(key)
    if not profiles:
        return SERVE_FLAGS[key]
    chosen = profile or os.environ.get("VLM_GPU_PROFILE") or "32gb"
    if chosen not in profiles:
        raise PaddleVastError(f"gpu_profile_unknown:{chosen}")
    return profiles[chosen]


def serve_command(key: str, profile: str | None = None) -> str:
    model = MODELS[key]
    if model.get("base"):
        adapter = os.environ.get("VLM_LORA_ADAPTER") or LORA_ADAPTER_DEFAULT
        base = MODELS[model["base"]]
        return (f"vllm serve {_local_dir(model['base'])} --served-model-name {base['served']} --host 127.0.0.1 --port {PORTS[key]} "
                f"--download-dir {MODELS_DIR} --lora-modules {model['served']}={adapter} {serve_flags(key, profile)}")
    return (f"vllm serve {_local_dir(key)} --served-model-name {model['served']} --host 127.0.0.1 --port {PORTS[key]} "
            f"--download-dir {MODELS_DIR} {serve_flags(key, profile)}")


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
                errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)


def _remote_script(script: str) -> str:
    """A shell script carried as base64 so no quote, dollar or backslash depends on the local argv parser
    (Windows OpenSSH from a hidden process mangled a quoted command and hung the remote shell)."""
    import base64

    return "echo " + base64.b64encode(script.encode("utf-8")).decode("ascii") + " | base64 -d | bash"


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
                f"for k in a b b9 b27 worker; do if [ -f {REMOTE_DIR}/$k.pid ] && kill -0 $(cat {REMOTE_DIR}/$k.pid) 2>/dev/null; "
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


def train_bundle_paths() -> list[str]:
    """What the trainer needs beside the dataset: the `vlm` package (pure Python) and the host script."""
    package = sorted(str(p).replace("\\", "/") for p in Path("vlm").glob("*.py"))
    return package + ["tools/vlm_train_lora.py", "tools/vlm_render_silver.py"]


TRAIN_REMOTE_DIR = "/workspace/lora-01"
TRAIN_LOCAL_ROOT = Path("discovery_reports/train13-logs/p3train")
CHECKPOINT_MARKER = "training_state.json"   # the resume-capable trainer writes it LAST in save_checkpoint
CHECKPOINT_REQUIRED = ("adapter_model.safetensors", "adapter_config.json")   # PEFT save_pretrained writes adapter_config.json LAST
CHECKPOINT_MIN_AGE_SECONDS = 30.0   # a weights-only save (no marker) counts as finished only once nothing in it changed for this long
AGE_KEY = "__age_seconds"
FULL_STATE_FILES = ("optimizer.pt", "rng.pt")
BASE_CONFIG_FILES = ("config.json", "generation_config.json", "chat_template.jinja", "preprocessor_config.json",
                     "video_preprocessor_config.json", "tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt", "LICENSE")


VERSION_PROBE = """import sys, importlib.metadata as m
print("python", sys.version.split()[0])
for n in ("torch", "transformers", "peft", "accelerate", "pillow", "safetensors", "vllm"):
    try:
        print(n, m.version(n))
    except m.PackageNotFoundError:
        print(n, "absent")
"""


def _scp_pull_command(settings, remote_path: str, local_path: str) -> list[str]:
    return ["scp", "-o", "BatchMode=yes", "-P", str(settings.vast_ssh_port),
            f"{settings.vast_ssh_user}@{settings.vast_host}:{remote_path}", local_path]


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def remote_checkpoints(settings, runner, remote_dir: str = TRAIN_REMOTE_DIR) -> dict[str, dict[str, int]]:
    """{adapter dir name: {file: size}} for every adapter-* directory under the run's output directory."""
    script = (f"cd {_shell_quote(remote_dir)} 2>/dev/null || exit 0; NOW=$(date +%s); for d in adapter-*; do [ -d \"$d\" ] || continue; "
              f"echo \"DIR $d $((NOW - $(stat -c %Y \"$d\")))\"; "
              f"(cd \"$d\" && for f in *; do [ -f \"$f\" ] && echo \"F $(stat -c %s \"$f\") $((NOW - $(stat -c %Y \"$f\"))) $f\"; done); done")
    out: dict[str, dict[str, int]] = {}
    current = None
    for line in (_ssh(settings, runner, _remote_script(script), timeout=120.0).stdout or "").splitlines():
        if line.startswith("DIR "):
            _, current, age = line.split(" ", 2)
            out[current] = {AGE_KEY: int(age)}
        elif line.startswith("F ") and current is not None:
            _, size, age, name = line.split(" ", 3)
            out[current][name] = int(size)
            out[current][AGE_KEY] = min(out[current][AGE_KEY], int(age))
    return out


def checkpoint_order(name: str) -> tuple:
    """Step checkpoints in step order, then adapter-final, then anything else by name."""
    if name.startswith("adapter-step-"):
        digits = name[len("adapter-step-"):]
        return (0, int(digits) if digits.isdigit() else 0, name)
    return (1, 0, name) if name == "adapter-final" else (2, 0, name)


def checkpoint_complete(files: dict[str, int]) -> bool:
    """Finished: the weights and the config (written last by PEFT) exist, and either the resume-capable trainer's
    marker exists too, or nothing in the directory has changed for CHECKPOINT_MIN_AGE_SECONDS (weights-only save)."""
    if not all(f in files for f in CHECKPOINT_REQUIRED):
        return False
    return CHECKPOINT_MARKER in files or files.get(AGE_KEY, 0) >= CHECKPOINT_MIN_AGE_SECONDS


def _sizes(files: dict[str, int]) -> dict[str, int]:
    return {k: v for k, v in files.items() if k != AGE_KEY}


def remote_hashes(settings, runner, remote_dir: str, name: str) -> dict[str, str]:
    proc = _ssh(settings, runner, _remote_script(f"cd {_shell_quote(remote_dir + '/' + name)} && sha256sum *"), timeout=900.0)
    hashes = {}
    for line in (proc.stdout or "").splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            hashes[parts[1].lstrip("*")] = parts[0]
    return hashes


def local_verified(local_dir: Path) -> dict | None:
    receipt = local_dir / "pull-receipt.json"
    if not receipt.is_file():
        return None
    data = json.loads(receipt.read_text(encoding="utf-8"))
    return data if data.get("verified") is True else None


def cmd_pull_adapter(settings, name: str, *, remote_dir: str = TRAIN_REMOTE_DIR, local_root: Path = TRAIN_LOCAL_ROOT,
                     run: str = "lora-01", runner: Callable[..., Any] = subprocess.run, sleeper: Callable[[float], None] = time.sleep,
                     settle_seconds: float = 20.0) -> dict:
    """Copy one finished checkpoint off the instance and verify it file by file (size and sha256 at both ends).

    Refuses an unfinished save (no training_state.json) or one still being written (sizes change across a settle pause).
    A verified local copy is never overwritten; an unverified leftover is moved aside, never merged into.
    """
    first = remote_checkpoints(settings, runner, remote_dir)
    if name not in first:
        raise PaddleVastError(f"checkpoint_missing:{name}")
    if not checkpoint_complete(first[name]):
        raise PaddleVastError(f"checkpoint_incomplete:{name}")
    sleeper(settle_seconds)
    second = remote_checkpoints(settings, runner, remote_dir).get(name)
    if second is None or _sizes(second) != _sizes(first[name]):
        raise PaddleVastError(f"checkpoint_unsettled:{name}")
    sizes = _sizes(second)
    hashes = remote_hashes(settings, runner, remote_dir, name)
    if set(hashes) != set(sizes):
        raise PaddleVastError(f"checkpoint_hash_listing_mismatch:{name}")
    local_dir = Path(local_root) / run / name
    existing = local_verified(local_dir)
    if existing is not None:
        return {"name": name, "status": "already_verified", "local_dir": str(local_dir), "pulled_at": existing["pulled_at"],
                "files": existing["files"]}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if local_dir.exists():
        local_dir.rename(local_dir.with_name(f"{name}.unverified-{stamp}"))
    incoming = local_dir.with_name(f"{name}.incoming-{stamp}")
    incoming.mkdir(parents=True)
    files = {}
    for fname in sorted(sizes):
        target = incoming / fname
        _run(runner, _scp_pull_command(settings, f"{remote_dir}/{name}/{fname}", str(target)), capture_output=True, text=True, timeout=7200)
        if not target.is_file():
            raise PaddleVastError(f"pull_missing:{fname}")
        size = target.stat().st_size
        digest = _sha256_file(target)
        if size != sizes[fname]:
            raise PaddleVastError(f"pull_size_mismatch:{fname}:{size}!={sizes[fname]}")
        if digest != hashes[fname]:
            raise PaddleVastError(f"pull_hash_mismatch:{fname}")
        files[fname] = {"bytes": size, "sha256": digest}
    step = None
    hyper = None
    if (incoming / CHECKPOINT_MARKER).is_file():
        state = json.loads((incoming / CHECKPOINT_MARKER).read_text(encoding="utf-8"))
        step = state.get("step")
        hyper = state.get("hyperparameters")
    receipt = {"name": name, "run": run, "remote_dir": remote_dir, "step": step, "hyperparameters": hyper, "files": files,
               "full_state": all(f in files for f in FULL_STATE_FILES),
               "resume_note": ("optimizer moments and RNG streams present: full-state resume" if all(f in files for f in FULL_STATE_FILES)
                               else "weights-only for resume: schedule position and counters come from training_state.json, optimizer moments and RNG streams restart"),
               "verified": True, "verification": "size and sha256 compared at source (sha256sum on the instance) and destination for every file",
               "pulled_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (incoming / "pull-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    incoming.rename(local_dir)
    return {**receipt, "status": "pulled", "local_dir": str(local_dir)}


def cmd_pull_run_files(settings, *, remote_dir: str = TRAIN_REMOTE_DIR, local_root: Path = TRAIN_LOCAL_ROOT, run: str = "lora-01",
                       runner: Callable[..., Any] = subprocess.run) -> dict:
    """The run's small files (train receipt(s) and the log) copied next to the checkpoints, hash-verified."""
    listing = _ssh(settings, runner, _remote_script(f"cd {_shell_quote(remote_dir)} 2>/dev/null && ls -1 train-receipt-*.json 2>/dev/null; "
                                                    f"ls -1 {_shell_quote(remote_dir + '.log')} 2>/dev/null"), timeout=60.0).stdout or ""
    out = {}
    target_dir = Path(local_root) / run
    target_dir.mkdir(parents=True, exist_ok=True)
    for entry in [l.strip() for l in listing.splitlines() if l.strip()]:
        remote_path = entry if entry.startswith("/") else f"{remote_dir}/{entry}"
        local_name = Path(entry).name if not entry.endswith(".log") else "train.log"
        expected = (_ssh(settings, runner, _remote_script(f"sha256sum {_shell_quote(remote_path)}"), timeout=120.0).stdout or "").split()[:1]
        target = target_dir / local_name
        _run(runner, _scp_pull_command(settings, remote_path, str(target)), capture_output=True, text=True, timeout=600)
        digest = _sha256_file(target) if target.is_file() else None
        out[local_name] = {"sha256": digest, "verified": bool(expected) and digest == expected[0]}
    return out


def cmd_watch_adapters(settings, *, remote_dir: str = TRAIN_REMOTE_DIR, local_root: Path = TRAIN_LOCAL_ROOT, run: str = "lora-01",
                       interval_seconds: float = 300.0, deadline_seconds: float = 16 * 3600, runner: Callable[..., Any] = subprocess.run,
                       sleeper: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                       emit: Callable[[dict], None] | None = None) -> dict:
    """Poll the run directory and copy every finished checkpoint off the instance as soon as it is complete.

    Ends when adapter-final is verified locally and the train receipt is copied, or at the deadline. A failed poll or
    pull is logged and retried on the next interval; it never stops the watch and never touches the trainer.
    """
    emit = emit or (lambda event: print(json.dumps(event), flush=True))
    started = clock()
    pulled: dict[str, str] = {}
    final_done = False
    while True:
        try:
            listing = remote_checkpoints(settings, runner, remote_dir)
            for name in sorted(listing, key=checkpoint_order):
                if name in pulled or not checkpoint_complete(listing[name]):
                    continue
                result = cmd_pull_adapter(settings, name, remote_dir=remote_dir, local_root=local_root, run=run, runner=runner, sleeper=sleeper)
                pulled[name] = result["local_dir"]
                emit({"event": result["status"], "name": name, "step": result.get("step"), "local_dir": result["local_dir"],
                      "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
            if "adapter-final" in pulled and not final_done:
                files = cmd_pull_run_files(settings, remote_dir=remote_dir, local_root=local_root, run=run, runner=runner)
                final_done = any(k.startswith("train-receipt-") and v["verified"] for k, v in files.items())
                emit({"event": "run_files", "files": files, "final_done": final_done})
                if final_done:
                    break
            emit({"event": "poll", "checkpoints": {k: checkpoint_complete(v) for k, v in listing.items()}, "pulled": sorted(pulled),
                  "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        except PaddleVastError as exc:
            emit({"event": "error", "code": _mask(str(exc), settings), "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        if clock() - started >= deadline_seconds:
            emit({"event": "deadline", "pulled": sorted(pulled)})
            break
        sleeper(interval_seconds)
    return {"pulled": pulled, "final_done": final_done}


def cmd_recovery_bundle(settings, *, local_root: Path = TRAIN_LOCAL_ROOT, run: str = "lora-01", base_key: str = "b27bf16",
                        remote_dir: str = TRAIN_REMOTE_DIR, runner: Callable[..., Any] = subprocess.run) -> dict:
    """Everything a restore needs besides the adapter weights, copied once per run into <run>/recovery/: the base model's
    identity (repo, commit, config hashes), its processor/tokenizer/chat-template files (hash-verified), the trainer's
    source hashes, the training command line, and the host's software versions. Nothing customer-related travels."""
    base_dir = _local_dir(base_key)
    target = Path(local_root) / run / "recovery"
    target.mkdir(parents=True, exist_ok=True)
    meta = _ssh(settings, runner, _remote_script(f"cd {_shell_quote(base_dir)} && cat .cache/huggingface/download/config.json.metadata 2>/dev/null | head -c 400; "
                                                 f"echo; echo ===; sha256sum config.json *.safetensors 2>/dev/null"), timeout=900.0).stdout or ""
    head, _, weight_hashes = meta.partition("===")
    commit = next((l.split()[-1] for l in head.splitlines() if len(l.split()[-1]) == 40), None)
    files = {}
    for fname in BASE_CONFIG_FILES:
        expected = (_ssh(settings, runner, _remote_script(f"sha256sum {_shell_quote(base_dir + '/' + fname)} 2>/dev/null"), timeout=120.0).stdout or "").split()[:1]
        if not expected:
            files[fname] = {"present": False}
            continue
        local_path = target / "base-config" / fname
        local_path.parent.mkdir(parents=True, exist_ok=True)
        _run(runner, _scp_pull_command(settings, f"{base_dir}/{fname}", str(local_path)), capture_output=True, text=True, timeout=600)
        digest = _sha256_file(local_path) if local_path.is_file() else None
        files[fname] = {"present": True, "sha256": digest, "verified": digest == expected[0]}
    versions = _ssh(settings, runner, _remote_script(
        f"PID=$(cat {_shell_quote(remote_dir + '.pid')} 2>/dev/null); [ -n \"$PID\" ] && tr '\\0' ' ' < /proc/$PID/cmdline; echo; echo ===; "
        f"{PADDLE_PYTHON} -c {_shell_quote(VERSION_PROBE)} 2>/dev/null; "
        "nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null; "
        "cd /workspace/ci_train && sha256sum vlm_train_lora.py vlm/train_lora.py vlm/prompts.py vlm/schema.py 2>/dev/null"), timeout=120.0).stdout or ""
    cmdline, _, environment = versions.partition("===")
    from vlm.prompts import PROMPT_VERSION, stage_b_prompt

    previous_path = target / "recovery-manifest.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.is_file() else {}
    command = _mask(cmdline.strip(), settings) or previous.get("training_command")
    manifest = {"run": run, "remote_dir": remote_dir, "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "base": {"key": base_key, "repo": MODELS[base_key]["repo"], "commit": commit, "remote_dir": base_dir,
                         "weight_hashes": [l for l in weight_hashes.strip().splitlines() if l.strip()]},
                "base_config_files": files,
                "training_command": command or None,
                "train_receipts_local": sorted(p.name for p in (Path(local_root) / run).glob("train-receipt-*.json")),
                "host_environment": [l for l in environment.strip().splitlines() if l.strip()],
                "prompt": {"version": PROMPT_VERSION, "stage_b_prompt_example": stage_b_prompt(page_number=1, page_total=1),
                           "chat_template": "processor.apply_chat_template(..., enable_thinking=False); prompt tokens masked; assistant target = canonical JSON"},
                "adapters_local": sorted(p.name for p in (Path(local_root) / run).glob("adapter-*") if local_verified(p) is not None),
                "note": "checkpoints of this run carry optimizer.pt and rng.pt when saved by the resume-capable trainer; a checkpoint without them is weights-only for resume"}
    (target / "recovery-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {**manifest, "manifest": str(target / "recovery-manifest.json")}


def cmd_deploy_train(settings, dataset: Path | None, *, runner: Callable[..., Any] = subprocess.run) -> dict:
    """R17: ship the trainer and, when given, the silver dataset to /workspace on the rented host. Code goes as
    a tar stream over SSH (the `vlm` package beside the script); the dataset (JPEG pages + JSONL targets, customer
    derived) goes the same way and stays on the host and the local machine only."""
    import tarfile
    import tempfile

    remote_train = "/workspace/ci_train"
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "train-bundle.tar"
        with tarfile.open(bundle, "w") as tar:
            for path in train_bundle_paths():
                arc = path.split("/")[-1] if path.startswith("tools/") else path
                tar.add(path, arcname=arc)
        _ssh(settings, runner, f"mkdir -p {remote_train}")
        _run(runner, _scp_command(settings, str(bundle), f"{remote_train}/train-bundle.tar"), capture_output=True, text=True, timeout=600)
        _ssh(settings, runner, f"cd {remote_train} && tar -xf train-bundle.tar && rm train-bundle.tar")
    out = {"deployed": True, "remote": remote_train, "files": len(train_bundle_paths())}
    if dataset is not None:
        dataset = Path(dataset)
        if not (dataset / "manifest.json").is_file():
            raise PaddleVastError("dataset_manifest_missing")
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "dataset.tar"
            with tarfile.open(archive, "w") as tar:
                tar.add(str(dataset), arcname=dataset.name)
            size_gb = archive.stat().st_size / 1e9
            free = _disk_free_gb(settings, runner)
            if free < size_gb * 2 + DISK_MARGIN_GB:
                raise PaddleVastError(f"disk_insufficient:{free:.0f}GB_free_for_{size_gb:.1f}GB_dataset")
            _run(runner, _scp_command(settings, str(archive), f"/workspace/{dataset.name}.tar"), capture_output=True, text=True, timeout=7200)
            _ssh(settings, runner, f"cd /workspace && tar -xf {dataset.name}.tar && rm {dataset.name}.tar", timeout=1800)
        out["dataset"] = {"name": dataset.name, "remote": f"/workspace/{dataset.name}", "tar_gb": round(size_gb, 2)}
    return out


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
                                            "tunnel-down", "attest", "deploy-train", "pull-adapter", "watch-adapters", "recovery-bundle"))
    parser.add_argument("--key", choices=("a", "b", "b9", "b27", "b27bf16", "b27ft", "b27lora", "worker", "all"), default=None)
    parser.add_argument("--dataset", default=None, help="deploy-train: the local silver dataset directory to ship")
    parser.add_argument("--since-epoch", type=float, default=0.0)
    parser.add_argument("--name", default=None, help="pull-adapter: the checkpoint directory name (adapter-step-00100, adapter-final)")
    parser.add_argument("--remote-dir", default=TRAIN_REMOTE_DIR)
    parser.add_argument("--run", default="lora-01")
    parser.add_argument("--interval-seconds", type=float, default=300.0)
    parser.add_argument("--deadline-hours", type=float, default=16.0)
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
        elif args.command == "deploy-train":
            out = cmd_deploy_train(settings, Path(args.dataset) if args.dataset else None)
        elif args.command == "pull-adapter":
            if not args.name:
                raise PaddleVastError("name_required")
            out = cmd_pull_adapter(settings, args.name, remote_dir=args.remote_dir, run=args.run)
        elif args.command == "watch-adapters":
            out = cmd_watch_adapters(settings, remote_dir=args.remote_dir, run=args.run, interval_seconds=args.interval_seconds,
                                     deadline_seconds=args.deadline_hours * 3600.0)
        elif args.command == "recovery-bundle":
            out = cmd_recovery_bundle(settings, run=args.run, remote_dir=args.remote_dir)
        else:
            out = cmd_attest(settings, since_epoch=args.since_epoch)
    except PaddleVastError as exc:
        print(json.dumps({"error": _mask(str(exc), settings)}))
        return 1
    print(_mask(json.dumps(out, indent=2), settings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
