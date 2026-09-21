# Phase 3.1 — instance scripts for the two-model pair

These three scripts run **on the rented GPU instance**, not on a workstation. They assume the remote
root `/workspace/bank-statement-shootout` and are committed here so a fresh clone carries them; they
were already installed and run on the instance on 2026-09-21.

The instance address, port, host-key fingerprint and SSH alias are **not** in this repository. See
`docs/agent-handoffs/PHASE3-FALLBACK-CONNECTION.example.md` for the shape of the annex and ask
Gustavo for the filled-in copy.

| script | what it does |
|---|---|
| `install_pair_env.sh` | builds `envs/vllm` (vLLM 0.29.0), installs the CUDA 13 toolkit that the FlashInfer JIT needs on Blackwell, and downloads both models at their pinned revisions. Idempotent. |
| `serve_pair.sh` | `start`, `stop` or `status` for both servers. Stage A on port 18013 at `gpu_memory_utilization 0.20`, Stage B on 18022 at `0.55`, both loopback only, both resident at once. |
| `smoke_pair.py` | sends one page image to each server and prints status only — HTTP code, finish reason, character and token counts, elapsed seconds. Never prints page content, so it is safe to run from a hosted coding session. |

Pinned model revisions, which are the exact ones that produced the leaderboard in
`docs/moneythumb-replacement/phase3/shootout/`:

```
rednote-hilab/dots.mocr        e539fbb52280393adc081b289ec597430a0f9031
nvidia/Qwen3.8-27B-NVFP4       482ca0f3832238542f8f5295dde86b5f22711d80
```

Do not float either revision. Serving flags match the benchmark run
(`--max-model-len 32768 --max-num-seqs 2 --limit-mm-per-prompt.image 1 --no-enable-prefix-caching`,
`--trust-remote-code` for Stage A only, `VLLM_USE_FLASHINFER_SAMPLER=0`). Raising `--max-num-seqs`
for throughput is a separate change that has to be re-validated, because batching can perturb
numerics even at temperature 0.

**Before building on dots.mocr, read the licence item in the handoff.** Its Hugging Face tag says
MIT; the file shipped inside the weights is a custom agreement with an acceptable-use clause that
covers documents containing financial personal data. That needs a ruling.

Typical sequence on a fresh instance:

```bash
cd /workspace/bank-statement-shootout
bash artifacts/install_pair_env.sh            # once, ~20 minutes including downloads
bash artifacts/serve_pair.sh start            # ~8 minutes to load both models
envs/vllm/bin/python artifacts/smoke_pair.py  # status-only check
bash artifacts/serve_pair.sh stop
```
