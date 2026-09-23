#!/usr/bin/env bash
# Starts both Phase 3.1 model servers on the instance, loopback only, and waits until each is ready.
#   bash artifacts/serve_pair.sh start | stop | stop-a | stop-b | status
# Stage A = dots.mocr on 18013, Stage B = Qwen3.8-27B-NVFP4 on 18022.
# Serving flags are identical to the 2026-09-20 shootout run so results stay comparable, except the number of
# sequences each server runs at once: SEQS_A / SEQS_B (default 2, the shootout's). The reviewer is decode-bound, so
# more sequences raise throughput; batching can perturb numerics even at temperature 0, so a run records its values.
#   SEQS_A=4 SEQS_B=6 bash artifacts/serve_pair.sh start
# `start` leaves a server already up untouched: stop it first (stop-a or stop-b stops one server) to change its value.
set -uo pipefail
SEQS_A=${SEQS_A:-2}
SEQS_B=${SEQS_B:-2}
ROOT=/workspace/bank-statement-shootout
export HF_HOME=$ROOT/models/hf_home
export HF_HUB_OFFLINE=1
export VLLM_USE_FLASHINFER_SAMPLER=0
export CUDA_HOME=/usr/local/cuda-13.0
export PATH=/usr/local/cuda-13.0/bin:$PATH
export VLLM_NO_USAGE_STATS=1
export DO_NOT_TRACK=1
PY=$ROOT/envs/vllm/bin/python
LOGS=$ROOT/artifacts/logs
mkdir -p "$LOGS"

A_DIR="$HF_HOME/hub/models--rednote-hilab--dots.mocr/snapshots/e539fbb52280393adc081b289ec597430a0f9031"
B_DIR="$HF_HOME/hub/models--nvidia--Qwen3.8-27B-NVFP4/snapshots/482ca0f3832238542f8f5295dde86b5f22711d80"

start_one() {
  local name=$1 port=$2 model=$3 util=$4 seqs=$5; shift 5
  if curl -sf "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1; then
    echo "$name already up on $port"; return 0
  fi
  echo "starting $name on $port from $model with --max-num-seqs $seqs"
  nohup "$PY" -m vllm.entrypoints.openai.api_server --model "$model" --served-model-name "$name" \
    --host 127.0.0.1 --port "$port" --max-model-len 32768 --max-num-seqs "$seqs" \
    --gpu-memory-utilization "$util" --limit-mm-per-prompt.image 1 --no-enable-prefix-caching "$@" \
    > "$LOGS/serve-$name.log" 2>&1 < /dev/null &
  echo "$!" > "$LOGS/serve-$name.pid"
}

wait_one() {
  local name=$1 port=$2 tries=0
  while [ $tries -lt 180 ]; do
    if curl -sf "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1; then echo "$name READY on $port"; return 0; fi
    if ! kill -0 "$(cat "$LOGS/serve-$name.pid" 2>/dev/null)" 2>/dev/null; then
      echo "$name DIED, last log lines:"; tail -15 "$LOGS/serve-$name.log"; return 1
    fi
    sleep 10; tries=$((tries+1))
  done
  echo "$name TIMEOUT after 30 min"; tail -15 "$LOGS/serve-$name.log"; return 1
}

case "${1:-start}" in
  start)
    [ -d "$A_DIR" ] || { echo "missing dots.mocr snapshot"; exit 2; }
    [ -d "$B_DIR" ] || { echo "missing Qwen NVFP4 snapshot"; exit 2; }
    start_one dotsmocr 18013 "$A_DIR" 0.20 "$SEQS_A" --trust-remote-code
    wait_one dotsmocr 18013 || exit 1
    start_one qwen3.8-27b-nvfp4 18022 "$B_DIR" 0.55 "$SEQS_B"
    wait_one qwen3.8-27b-nvfp4 18022 || exit 1
    nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
    echo "both servers ready"
    ;;
  stop|stop-a|stop-b)
    case "$1" in stop-a) names=dotsmocr ;; stop-b) names=qwen3.8-27b-nvfp4 ;; *) names="dotsmocr qwen3.8-27b-nvfp4" ;; esac
    for n in $names; do
      if [ -f "$LOGS/serve-$n.pid" ]; then
        pid=$(cat "$LOGS/serve-$n.pid")
        kill "$pid" 2>/dev/null && echo "stopping $n"
        for _ in $(seq 60); do kill -0 "$pid" 2>/dev/null || break; sleep 2; done
        kill -0 "$pid" 2>/dev/null && echo "$n still running after 120 s" || echo "stopped $n"
        rm -f "$LOGS/serve-$n.pid"
      fi
    done
    ;;
  status)
    for p in 18013 18022; do
      printf "%s: " "$p"; curl -sf "http://127.0.0.1:$p/v1/models" | head -c 200 || echo "down"; echo
    done
    nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
    ;;
esac
