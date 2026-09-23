# Phase 3.1 — instance scripts for the two-model pair

The installation, serving and smoke scripts run **on the rented GPU instance**. They assume the remote
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
`--trust-remote-code` for Stage A only, `VLLM_USE_FLASHINFER_SAMPLER=0`). `--max-num-seqs` is the one
exception: `SEQS_A` / `SEQS_B` set it per server (default 2, the benchmark's). The reviewer is
decode-bound (about a thousand generated tokens per call), so runs over many statements serve more
sequences at once (`SEQS_A=4 SEQS_B=8`); batching can perturb numerics even at temperature 0, so note the
values a run was served with in its ledger (nothing records them automatically; the server log and
`/metrics` show them). `stop-a` / `stop-b` stop one server, and `start` leaves a server that is already
up untouched.

dots.mocr's custom licence was accepted by Gustavo on 2026-09-21; the pinned
revision and acceptance are recorded in `docs/moneythumb-replacement/phase3/LICENSES.md`.

Typical sequence on a fresh instance:

```bash
cd /workspace/bank-statement-shootout
bash artifacts/install_pair_env.sh            # once, ~20 minutes including downloads
bash artifacts/serve_pair.sh start            # ~8 minutes to load both models
envs/vllm/bin/python artifacts/smoke_pair.py --page synthetic/pages/example.png
bash artifacts/serve_pair.sh stop
```

Use an existing synthetic PNG for `--page`; the smoke script refuses paths
outside the synthetic fixture tree and has no customer-document default.

## Synthetic pipeline wiring check

`check_synthetic.py` runs **from the repository environment**, with the two
loopback endpoints available. Use the supplied private `synthetic/manifest.json`
unchanged: its `manifest_version: 1`, `scope: "synthetic"`, and `docs` entries
bind each fixture through `source_rel` and `source_sha256`. The checker also
accepts this compact manifest format, with paths relative to the synthetic
fixture directory and their SHA256 hashes:

```json
{"version":1,"data_scope":"synthetic","files":[{"path":"pdfs/example.pdf","sha256":"<sha256>"}]}
```

The caller also pins the manifest's own SHA256. All one to three PDFs must match
before any request is sent. Output must be outside the worktree or under the
gitignored `.claude` runtime directory; the cold recovery tree is refused.

```bash
.venv/bin/python tools/phase3_pair/check_synthetic.py \
  --manifest /private/fixtures/synthetic/manifest.json \
  --manifest-sha256 <manifest-sha256> \
  --synthetic-root /private/fixtures/synthetic \
  --output-dir /private/pair-wiring
```

The checker reports counts and status only, saves full evidence privately, and
appends a run entry to the output directory's `RUN_STATE.md`. It exercises the
analysis adapter on fabricated fixtures with explicit gated admission; this
does not change the webapp's remote authorization or publication policy.

## Bounded real-page judgment check

`check_judgment.py` runs exactly two or three explicitly selected real PDFs after
the owner authorizes that evaluation. It requires the existing customer-data
opt-in in its process environment; it does not enable it for the webapp. Bind
both the manifest and each PDF by SHA256:

```json
{"version":1,"scope":"real_judgment","documents":[{"id":"J01","path":"relative.pdf","sha256":"<sha256>"},{"id":"J02","path":"other.pdf","sha256":"<sha256>"}]}
```

```bash
.venv/bin/python tools/phase3_pair/check_judgment.py \
  --manifest /private/judgment/manifest.private.json \
  --manifest-sha256 <manifest-sha256> \
  --source-root /private/statements \
  --output-dir /private/judgment/results
```

All inputs are verified before the first request. Only rendered page requests
travel through the loopback model endpoints; the tool creates no remote files.
Verify that request/output content logging is disabled on the servers and clear
their multimodal caches after evaluation. Full evidence and native-text
corroboration stay private. Console output contains page progress and counts.
An offline analysis is attempted only for gate-admitted evidence; this publishes
no webapp job and changes no publication policy. Exit status `2` means at least
one document was held or failed analysis.

Native substring matches do not prove complete descriptions, and deterministic
parser results are corroboration rather than ground truth. Source-page review
is necessary before claiming that corrections improve reading quality. These
bounded checks are not a corpus replay or a leaderboard score.

After a complete run, build the private source viewer from its exact run folder:

```bash
.venv/bin/python tools/phase3_pair/review_judgment.py \
  --manifest /private/judgment/manifest.private.json \
  --manifest-sha256 <manifest-sha256> \
  --source-root /private/statements \
  --run-dir /private/judgment/results/<run-id> \
  --output-dir /private/judgment/source-review
```

The viewer renders only the selected PDFs locally and shows each source page
beside original, corrected and retained row evidence. It includes every row
state, all field changes and the held gate status. It reads no analysis metrics
and makes no inference calls. Serve its output directory on loopback for local
review, or open `review.html` locally. Human verdicts remain in browser storage
until exported as private JSON; they do not authorize webapp publication.
