#!/usr/bin/env bash
# Installs the serving environment and the two picked models on the current Vast instance.
# Idempotent: re-running skips what is already present. Log: artifacts/logs/install-vllm-env.log
set -uo pipefail
ROOT=/workspace/bank-statement-shootout
export DEBIAN_FRONTEND=noninteractive
export HF_HOME=$ROOT/models/hf_home
mkdir -p "$ROOT/artifacts/logs" "$ROOT/models/hf_home"

echo "=== started $(date -u +%FT%TZ)"
echo "=== gpu"; nvidia-smi --query-gpu=name,memory.total,compute_cap --format=csv,noheader

if [ ! -d /usr/local/cuda-13.0 ]; then
  echo "=== apt cuda-toolkit-13-0 (FlashInfer JIT needs >= 12.9 on Blackwell)"
  apt-get update -qq && apt-get install -y -qq cuda-toolkit-13-0
else
  echo "=== cuda-toolkit-13-0 already present"
fi

P=$ROOT/envs/vllm/bin/python
if [ ! -x "$P" ]; then
  echo "=== creating envs/vllm"
  python3 -m venv "$ROOT/envs/vllm"
fi

echo "=== pip"
$P -m pip install -q -U pip wheel setuptools
$P -m pip install -q vllm==0.29.0
$P -m pip install -q flashinfer-jit-cache==0.6.18+cu130 --extra-index-url https://flashinfer.ai/whl/cu130 || echo "WARN flashinfer-jit-cache wheel unavailable, JIT will build on first use"
$P -m pip install -q requests pillow huggingface_hub

echo "=== versions"
$P -c "import vllm,torch,transformers;print('VERSIONS', vllm.__version__, torch.__version__, transformers.__version__)"

echo "=== model download (pinned to the benchmarked revisions)"
$P - <<'PY'
from huggingface_hub import snapshot_download
PINS = [("rednote-hilab/dots.mocr", "e539fbb52280393adc081b289ec597430a0f9031"),
        ("nvidia/Qwen3.8-27B-NVFP4", "482ca0f3832238542f8f5295dde86b5f22711d80")]
for repo, rev in PINS:
    path = snapshot_download(repo_id=repo, revision=rev, max_workers=8)
    print("DOWNLOADED", repo, rev, path, flush=True)
PY

echo "=== disk"; df -h /workspace | tail -1
echo "=== finished $(date -u +%FT%TZ)"
