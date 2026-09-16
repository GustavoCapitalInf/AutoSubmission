# PADDLE_VAST_RUNBOOK — operating the Phase 2.1 PaddleOCR development endpoint

Authority: `docs/moneythumb-replacement/PHASE2_RULINGS.md` §"Phase 2.1 rulings and
authorization" (the explicit Vast.ai authorization, the DATA PRIVACY BOUNDARY) and
`docs/agent-handoffs/P21-PADDLE.md`. This runbook is operational, not a re-ruling: if
anything here conflicts with the rulings file, the rulings file wins.

## What this is

An explicitly authorized, explicitly opted-in, explicitly PAID development endpoint:
PaddleOCR 3.7.0 / PP-OCRv5 on a Vast.ai RTX 5090, reachable ONLY through an SSH tunnel
to a loopback port. It is not a production path. Nothing in the default test suite,
`corpus_gate.py`, the discovery runner's default modes, or the webapp calls it. It
exists to prove and measure the Paddle extractor on synthetic fixtures, and — only
with a separate ruling from Gustavo — eventually on the 13-document legal escalation
population (§"The 13-document remote-data ruling" below).

## The DATA PRIVACY BOUNDARY (read this before running anything)

* No document from `Bank Statements/`, `tests/corpus_cache/`, `discovery_reports/`, any
  recovery cache, or any real customer statement is ever sent to this endpoint.
* The ONLY bytes this pipeline sends anywhere are (a) synthetic fixtures rendered by
  `tests/paddle_synthetic.py` from literal synthetic strings, and (b) the worker script
  itself (`ocr/paddle_worker.py`), deployed by `tools/paddle_vast.py deploy`.
* The ONLY network egress this codebase's Paddle code performs is SSH/SCP to the host
  named by `PADDLE_VAST_HOST` and HTTP to `127.0.0.1:<tunnel port>`. No other host, ever.
* `tools/paddle_vast.py measure` refuses any fixture path under `Bank Statements/`,
  `tests/corpus_cache/` or `discovery_reports/` — by construction, not by convention.
* `ocr.paddle_rung.read_document` refuses a `data_scope="customer"` document on a
  `remote_paid` worker unless `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` is set to its exact
  literal. **Do not set that variable without Gustavo's separate remote-data / privacy /
  retention ruling.** Phase 2.1 never sets it.
* **What this boundary guarantees, precisely (`PHASE2_P21PADDLE_REVIEW.md` MAJOR-2).**
  `check_remote_authorization` and `PaddleClient`'s constructor both RE-DERIVE the two
  opt-in literals from the process environment at the moment of the check/construction —
  a `PaddleSettings` object whose OWN flags claim an opt-in, but whose environment does
  not actually carry the matching literal, is refused just the same as if the flag were
  false. So: **an honest caller whose settings came from `load_paddle_settings()` cannot
  send a `customer`-scope document to a `remote_paid` worker without the operator having
  set the real `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` literal in the real environment.**
  What it does NOT guarantee: nothing in this module verifies that a caller's declared
  `data_scope` truthfully describes the bytes it is sending — `data_scope` is a
  declaration, not a content check, because this module has no way to inspect where a
  caller's document came from. The one caller that matters in production —
  `discovery/runner.py`'s `--scanned-paddle` mode — always declares `data_scope="customer"`
  (never `"synthetic"`) because it reads the archive; that literal is pinned by cell R's
  own tests, not enforced by this module.

## Prerequisites

* SSH access to the Vast.ai instance, using your existing key (no key is ever copied
  into this repository).
* `PADDLE_VAST_HOST`, `PADDLE_VAST_SSH_PORT`, `PADDLE_VAST_SSH_USER` set in your local,
  gitignored `.env` (copy `.env.paddle.example` and fill in real values there — never
  edit the example file itself). `PADDLE_PROVIDER=vast.ai` and
  `PADDLE_EXECUTION_CLASS=remote_paid`.
* The remote interpreter named by `PADDLE_VAST_PYTHON` (default `/venv/main/bin/python`)
  already has `paddleocr==3.7.0`, `paddlepaddle-gpu`, Pillow and numpy installed, and the
  two PP-OCRv5 models cached (`PP-OCRv5_server_det`, `en_PP-OCRv5_mobile_rec`).
  `tools/paddle_vast.py check` verifies this without starting anything. **Install into an
  environment that belongs to another framework and you will break it** — see the
  2026-09-15 entry at the end of this runbook; that is what the variable exists for.
* Nothing binds to `0.0.0.0` on the remote host, ever. The worker refuses to start
  bound to anything but `127.0.0.1` (`ocr.paddle_worker.WorkerConfigError`). Never
  register the worker's port as a Vast "open port" and never front it with Caddy —
  the SSH tunnel is the only transport.

## Lifecycle, in order

```
python -m tools.paddle_vast check       # env names present, GPU + package versions match the pins
python -m tools.paddle_vast deploy      # scp's ocr/paddle_worker.py, runs --self-check remotely
python -m tools.paddle_vast start       # launches the worker under nohup, detached, token-protected
python -m tools.paddle_vast tunnel-up   # opens the SSH -L tunnel as a detached process
python -m tools.paddle_vast status      # masked settings + probe() result + tunnel liveness
python -m tools.paddle_vast measure     # the runtime/cost measurement (synthetic fixtures ONLY)
python -m tools.paddle_vast stop        # stops the REMOTE worker process
python -m tools.paddle_vast tunnel-down # closes the local SSH tunnel
```

`stop` and `tunnel-down` are separate on purpose: `stop` ends the remote PaddleOCR
process (which is what actually costs GPU time); `tunnel-down` ends the local SSH
forward. Run both at the end of any session — **nothing from this pipeline is left
running unattended.**

**Authentication needs no manual step.** `start` writes a per-session token to
`<runtime_dir>/worker.token` (gitignored) and exports it to the remote worker; every
LATER command in this sequence (`status`, the live test, `measure`) calls
`load_paddle_settings()` fresh, which falls back to reading that same file when
`PADDLE_WORKER_TOKEN` is not set in the environment — so the sequence above
authenticates correctly exactly as written, with no `export PADDLE_WORKER_TOKEN=...`
step of your own (`PHASE2_P21PADDLE_REVIEW.md` MAJOR-4). If `start` is run again after a
`stop`, it reuses the token already on file rather than minting a new one.

Every subcommand's OWN printed/returned output is masked (`tools.paddle_vast.mask_text`):
the real host, SSH user and worker token never appear in a log line, a report, or this
runbook. Where an example below shows a host, it is literally `<HOST>`.

## Setting the remote opt-in (only for a LIVE run)

`PADDLE_REMOTE_OPT_IN=I_ACCEPT_REMOTE_PAID_PADDLE_OCR` — set this ONLY in the
environment of the specific command you are about to run (never in a tracked file, never
exported for the whole shell session by habit). Its absence is the safe default: every
Paddle code path refuses before sending a byte when it is unset (CASE 13).

## Running the live proof

`tests/test_paddle_live.py` is marked `@pytest.mark.live` and `skipif`'d unless
`load_paddle_settings()` succeeds, the opt-in literal is set, and `probe()` reports the
worker available — so it is deselected by every other proof-floor run. To run it once,
over the real tunnel, on the synthetic image-only PDF:

```
PADDLE_REMOTE_OPT_IN=I_ACCEPT_REMOTE_PAID_PADDLE_OCR \
  python -m pytest tests/test_paddle_live.py -m live -q
```

## The 13-document remote-data ruling

The Phase 2.0 run of record names 13 documents as the currently admitted extraction-
escalation population (R = 13, U-extract = 0). These are production customer
statements. D8 (`docs/agent-handoffs/PHASE2-1-PADDLE.md`) is explicit: Phase 2.1 does
NOT run them through Vast. If a future phase is authorized to do so, it requires:

1. Gustavo's explicit separate remote-data / privacy / retention ruling, recorded in
   `PHASE2_RULINGS.md` the same way the Phase 2.1 Vast authorization itself was;
2. `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` set to its exact literal for that run only;
3. the runner declaring `data_scope="customer"` (already the default in
   `discovery/runner.py`'s `--scanned-paddle` mode — see `docs/agent-handoffs/PHASE2-1-PADDLE.md`
   §"Extraction routing").

Until then, `remote_customer_data_refused` is the expected, correct outcome.

## Troubleshooting

* **`paddle_config_missing`** — a required `PADDLE_*` variable is absent; the error
  names it exactly. There is no default host, port or user.
* **`paddle_remote_opt_in_required`** — set `PADDLE_REMOTE_OPT_IN` for this command.
* **`paddle_runtime_mismatch`** — the worker's `/version` disagrees with the pins in
  `ocr/paddle_config.py` on at least one field (named in the exception). This means the
  remote environment drifted (a PaddleOCR/PaddlePaddle upgrade, a model swap) — do not
  relax the pin to make the error go away; review the drift first (the whole point of
  D5 is that a remote upgrade STOPS the rung until reviewed).
* **`paddle_worker_unreachable`** — a transport failure (connection refused, timeout,
  an HTTP error, a malformed or oversized response, or a redirect, which is always
  refused, never followed). Check `tunnel-up` succeeded and `status` shows
  `tunnel_running: true`.
* **A local port already listening** — `tunnel-up` refuses to stack a second tunnel on
  an already-listening local port; run `tunnel-down` first, or check for a stray SSH
  process from a previous session.

## What this is not

Not a production extraction path (Ruling A: automatic hosted extraction is refused —
nothing in `webapp/` or the auto-mode discovery runner calls Paddle). Not a $0 vendor
(actual paid GPU usage on this endpoint is measured, per the explicit authorization,
never invented from a rate table). Not a replacement for the deterministic validator
(Paddle produces evidence; it never decides a transaction, a sign, a balance, an
account, a currency, or `validated`).

## The Vast.ai Secure Cloud machine (2026-09-03) — the approved endpoint for Phase 2.3+

Gustavo provisioned a new Vast.ai **Secure Cloud** instance for every Phase 2.3+ Paddle run that
involves real customer statements; **the previous instance is retired for customer data.** Connection
details live ONLY in the local, gitignored `.env` (`PADDLE_VAST_HOST` / `PADDLE_VAST_SSH_PORT` /
`PADDLE_VAST_SSH_USER`; `PADDLE_PROVIDER=vast.ai`; `PADDLE_EXECUTION_CLASS=remote_paid`) — never in a
tracked file, never in a report. SSH authentication uses this machine's existing key (verified).

Brought up with the unchanged Phase 2.1 lifecycle on 2026-09-03: `check` (GPU RTX 5090 32,607 MiB,
driver 580.82.07; remote `/venv/main` paddleocr 3.7.0 / paddlepaddle 3.3.0 / Python 3.12.14;
`versions_match_pins: true`) → `deploy` (the worker's `/version` echoes provider `vast.ai`, class
`remote_paid`, PP-OCRv5, `PP-OCRv5_server_det` + `en_PP-OCRv5_mobile_rec`, the D5 switches,
`return_word_box: true`) → `start` (worker on the remote **loopback** port 8765) → `tunnel-up` (local
18765 → remote 127.0.0.1:8765) → `status` (`probe.available: false`, `paddle_remote_opt_in_required` —
the expected refusal without the literal) → the live proof `tests/test_paddle_live.py -m live` (1
passed) and `measure` (see `PADDLE_MEASUREMENTS.md` §"Secure Cloud machine") with the opt-in literal
set only in each command's own environment → a fail-closed probe (synthetic bytes declared
`data_scope="customer"` without the second literal → `PaddleRefused: remote_customer_data_refused`
before any connection; the same bytes as `synthetic` with the tunnel down → `paddle_worker_unreachable`,
so the authorization check precedes the transport) → `stop` + `tunnel-down` (`tunnel_running: false`).

**Port note.** The requested binding (worker on remote 127.0.0.1:8080, tunnel local 8080) is not used:
the instance's own Jupyter listens on `0.0.0.0:8080`, so the loopback worker keeps the Phase 2.1 default
8765 and the tunnel keeps the default local 18765 (deliberately a different number so "localhost" in a
log reads as a tunnel). The worker is never registered as a Vast open port and never fronted by the
instance's public listeners.

**For the 2.3 wave**: `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` is set ONLY in the environment of the
research-mode command, under the 2026-09-03 authorization recorded in `PHASE2_RULINGS.md`
§"Customer-data authorization — Paddle"; the worker retains nothing; stop the worker and tear the
tunnel down after each wave.

## The Phase 2.3 wave (P23-WAVE, cell W) — operating `tools/paddle_wave.py`

### Private custody and ordinary exports

New wave runs store original discovery artifacts under
`<research dir>/.wave/<partition>/discovery-runs/<population>/<session>/`.
The ordinary `run --out` root must be disjoint from the research root. It receives
only `wave_technical_rows.csv` and the completion marker `wave_export.json` in a
fresh session directory. No generic discovery report, path map, folder label,
statement field or billing object is copied there.

The versioned CSV preserves original row order and aliases, fingerprints, page
counts, closed source/cache statuses, a derived `wave_refusal_reason`, and technical
measurements. Missing measurements remain empty; `peak_rss_mb` may retain the
source-defined `not measured` sentinel. The marker binds the source session, both
original rows/provenance hashes, export hash, schema and row count. A consumer must
also supply the independently trusted source hashes/session; marker consistency
alone does not authenticate its source. Unknown fields/status values refuse.

State format 2 records each new chunk's custody marker and original hashes. The
loader also accepts format 1. Active legacy continuation advances to format 2;
a completed legacy resume retains format 1 and its existing zero-work session
audit. Reporting and offline export never rewrite historical state. Reports and
raster retention use the exact original custody rows. `report --out` identifies
the explicit historical raw root only for old markerless chunks, including mixed
old/new state; missing new custody never falls back to that root.

Successful extraction is saved before publication. A publication failure records
`export_status=failed` while retaining completed document outcomes and truthful
session counts. Retry that reporting operation offline into a fresh output root:

```text
python -m tools.paddle_wave export --run <exact closed custody session> \
  --out <fresh ordinary root> --data-dir <research dir> --config paddle-v5-prod \
  --population-name CTRL --session <recorded session basename> \
  --source-rows-sha256 <independently recorded original rows hash> \
  --source-provenance-sha256 <independently recorded original provenance hash>
```

This command does not call pending-document selection, an extractor, lifecycle
operations or state persistence. A directory without its completion marker is
incomplete; preserve it and use a fresh destination. Historical ordinary artifacts
and their scan findings remain private evidence. New safe exports do not change
the disposition of those original bytes.

This section is operational. The authority for running real customer statements on this
instance is `PHASE2_RULINGS.md` §"Customer-data authorization — Paddle" (2026-09-03, R1);
if anything here conflicts with that, the rulings file wins.

`tools/paddle_wave.py` is a thin orchestrator around the Phase 2.2 research mode. It never
reads a page: every page it causes to be read is read by `python -m discovery
--research-paddle`, through the same router, ladder and cache. It owns which documents are
studied, whether a study may start, and what the study produced.

```
python -m tools.paddle_wave populations --run <run-of-record dir> --out <populations dir>
python -m tools.paddle_wave preflight  --population <dir>/CTRL.shas --data-dir <research dir>
python -m tools.paddle_wave run        --population <dir>/CTRL.shas --data-dir <research dir> \
                                        --out <wave run dir> --root "<archive root>" \
                                        --chunk-size 50 --log <log path>
python -m tools.paddle_wave report     --data-dir <research dir> --populations-dir <dir> \
                                        --out <wave run dir>
```

**Set the two literals on the command itself, never in a shell profile, never in `.env`.**
`PADDLE_REMOTE_OPT_IN` and `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` must both carry their exact
authorized values in the environment of the `run` command; the wave refuses first and names
the missing one, and the research mode refuses again at its own door. Their absence is the
safe default.

**The configuration and its research partition.** `--config paddle-v5-prod` runs the Phase 2.1
production pins under a research partition of THE SAME NAME: the partition id is the
configuration block's name (Ocean's ruling of 2026-09-11 — the umbrella card's
`research/paddle-v5-prod` was prose the id's shape cannot carry, and a `research-` prefixed
rewrite is not the ruled id either). Cell V's `paddle-v5-orient` and `paddle-v6` are refused by
name, with their owner.

**The order is enforced, not remembered.** `CTRL` first, then `U755`, then `SLICE`. A later
population refuses to start while an earlier one still holds a document nothing has
attempted under the same configuration — the rule is read off the state files in the
research directory, so it survives a restart, a different shell and a different operator.

**Resuming.** Progress lives in `<research dir>/.wave/<partition>/<POPULATION>.json`, keyed by
content sha and written after every chunk. Re-run the same `run` command: documents that
produced evidence are skipped, documents that were REFUSED are attempted again (a refusal is
a counted finding, not a closed one), and any document the killed chunk had already finished
comes back as a cache hit under the same partition key. Nothing else needs to be told what
happened.

**Rotate the worker token before the first live session of a wave.** Delete the gitignored
`<runtime dir>/worker.token`; the next `start` mints a fresh one. Record the fact of the
rotation, never the value.

**Every session ends with the instance stopped and the tunnel closed**, and with the
retention attestation in the log: the worker's `/version` declares `retention: none` (read
BEFORE the stop — there is nothing to ask afterwards), and after the stop the instance is
inspected over SSH for a live worker process, a leftover pidfile, request artefacts and page
bytes under the worker's directory. The attestation COUNTS; it never lists a remote path. An
inspection that could not run fails the attestation, and `run` exits 3 rather than reporting
a clean instance it did not look at.

Two things the FIRST live session taught the attestation, both now in the instrument. The worker
process is given a bounded grace to finish dying before it is called alive (looked at every 5 s for
30 s; the record carries `probes`, so "it died on the second look" and "it was never alive" stay
different facts) — the CTRL run inspected about two seconds after `stop`, counted a process that was
already exiting, and reported a retention failure the instance did not have. And the `/tmp` image
count is scoped to files NEWER than the session start, because `/tmp` belongs to the whole image:
the same run counted one synthetic PNG an operator's own live test had left there two hours earlier.
That count is RECORDED, never gated — every gated count is inside the worker's own directory, which
this pipeline is the only writer of.

**Rasters.** Under the research partition the PNG of every page sent is kept at
`<research dir>/rasters/<content sha>/pNNNN.png`, and only when its sha256 reproduces the
`raster_sha256` the immutable evidence already records for that page — so a retained image is
provably the one the worker saw. Production partitions keep `raster_sha256` and no file. WHICH
read's pages are retained is answered by the cache's own index (the settings key the run
recorded), never by rebuilding a Paddle settings key here — so **give each configuration its own
`--data-dir`:** a research directory holding evidence-bearing reads of one document that record
DIFFERENT page rasters is refused, not guessed at.
These are customer page images: they live under the gitignored on-machine research area and
the archive's retention rule, and are never committed.

**What the report will not tell you.** No cost, rate, price or billing figure appears
anywhere in this tool: cost accounting is out of scope by Gustavo's ruling of 2026-09-03 and
the charges are his to track. The report's technical figures are latency (per document, and
the per-page mean), bytes up and down, VRAM as the worker sampled it, and the local peak RSS.

**Instance re-provisioned (2026-09-04).** The Secure Cloud machine was re-provisioned by Gustavo with a
new SSH port (same connection contract; only the gitignored `.env` changed). The unchanged lifecycle
re-proved it end to end: `check` (driver 580.105.08; paddleocr 3.7.0 / paddlepaddle 3.3.0 / Python
3.12.14; pins match) → `deploy` → `start` (loopback 8765) → `tunnel-up` (local 18765) → `status`
(refuses without the opt-in) → live proof 1 passed → `measure` (warm median 1,206 ms / p95 1,214 ms
end-to-end per synthetic page; inference ≈ 333 ms; VRAM 7,692 MiB) → `stop` + `tunnel-down`. The
instance's Jupyter still occupies 0.0.0.0:8080, so the port note above stands. No customer page sent.

**Instance re-created (2026-09-11) — the Phase 2.3 wave endpoint.** Gustavo brought up a NEW Secure Cloud
instance (new host and SSH port; only the gitignored `.env` changed; the old values timed out during the SSH
banner exchange — the signature of a stale Vast port mapping). Three things differed from the earlier
instances and are now the documented posture: (1) **SSH key** — a dedicated key pair
`~/.ssh/vast_5090_ed25519` (ed25519, no passphrase, because the tool runs `ssh` in BatchMode) is wired
through an `~/.ssh/config` `Host` block generated from the `.env` values (`IdentitiesOnly yes`); the public
key is registered on the instance by the operator; no key is ever copied into the repository. (2) **The
image is the plain Vast base image** (Ubuntu 24.04; `/venv/main` Python 3.12.14 with NO Paddle packages; CUDA
13.0 toolkit, driver 595.84): the pinned stack was installed by Ocean — `paddlepaddle-gpu==3.3.0` from the
`cu130` index (`https://www.paddlepaddle.org.cn/packages/stable/cu130/`, the only index carrying 3.3.0 for
CUDA 13) and `paddleocr==3.7.0` from PyPI (paddlex 3.7.2 follows) — and the two PP-OCRv5 models were
pre-downloaded so `deploy`'s 60-second self-check never pays the first fetch; `check` then reports
`versions_match_pins: true`. Package installs and model weights are not customer data. On this image
stop/start preserves the container; **recycle or destroy wipes it** (the stack, the models, any research
partition kept on the box) — prefer stop/start between waves. (3) **The GPU was shared** with a supervisor
service (`ocean-qwen-vision`: a vLLM server holding a 27B vision-language model, 29.8 GB of the 32.6 GB),
which made the worker's first `/ocr` fail with a CUDA allocation error (HTTP 500): not this program's
service (Phase 3 / Qwen is not authorized); at Gustavo's decision it was stopped and removed from supervisor
(its unit file backed up under `/root/removed-services-backup/` on the instance). Re-proved end to end
afterwards with the unchanged lifecycle: `check` (pins) → `deploy` (identity OK) → `start` (loopback 8765) →
`tunnel-up` (local 18765) → `status` (refuses without the literal) → `tests/test_paddle_live.py -m live`
**1 passed** (VRAM 7,704 MiB during inference; cold ≈ 4.0 s, warm ≈ 0.93 s end-to-end per 2550×3300
synthetic page) → `stop` → `tunnel-down`. Jupyter is not running on this image (supervisor shows it EXITED),
but the 8765 / 18765 defaults stay. No customer page sent by this proof; the Phase 2.3 wave runs
(`P23-WAVE.md`) follow under the 2026-09-03 authorization with both literals in each run's own environment.

**Instance replaced again (2026-09-15) — the Paddle-only wave endpoint, and two lessons worth more than the machine.**
The 2026-09-11 machine was gone (its port answered TCP and then timed out during the SSH banner exchange —
the signature of a stale Vast port mapping); Gustavo created a new one and registered a key. Only the
gitignored `.env` changed: host, port, user, and two NEW optional variables described below. What this
machine taught:

*1. Never install our pins into an image's shared environment without reading what already lives there.*
This image is a vLLM template: `/venv/main` carries torch 2.13.0+cu130 and vLLM 0.29.0, and the venv has
system-site-packages. Installing `paddlepaddle-gpu==3.3.0` there pulled `nvidia-cudnn-cu13 9.13.0.50` and
`nvidia-nccl-cu13 2.28.3` INTO the venv, where they shadowed the system versions torch needs (9.20.0.48 /
2.29.7) and broke it outright: `ImportError: … libtorch_cuda.so: undefined symbol: ncclCommResume`. The
install was stopped, every package it had added was uninstalled, and torch was verified working again
(`cuda available: True`) before anything else proceeded. **The lifecycle tool now names its interpreter**:
`tools/paddle_vast.py::remote_python()` reads `PADDLE_VAST_PYTHON` at the call site and falls back to
`/venv/main/bin/python`, so every earlier instance behaves exactly as before while an image like this one
keeps our stack in its own virtualenv (here: `/workspace/paddle-env`, which already carried the exact pins —
paddleocr 3.7.0, paddlepaddle-gpu 3.3.0, paddlex 3.7.2, CUDA 13.0, `run_check` green).
*Windows footnote:* Git bash rewrites POSIX-looking environment values into Windows paths when it spawns a
native process, which silently turned the remote path into `C:/Program Files/Git/workspace/...`. Setting
`MSYS2_ENV_CONV_EXCL=PADDLE_VAST_PYTHON` (both are documented in `.env.paddle.example`) keeps it intact.

*2. Choose the machine on its UPLOAD figure, not only its GPU.* The lifecycle proved green here — `check`
(pins match), `deploy` (self-check identity OK), `start` (loopback 8765), `tunnel-up` (local 18765),
`status` (refuses without the literal), `tests/test_paddle_live.py -m live` **1 passed** on the real GPU,
`measure`, `stop`, `tunnel-down` — but inference is 341 ms while a page takes **18.7 s end to end**.
Measured with incompressible bytes and no worker: **upload 46–77 KB/s**, download 1,361 KB/s, SSH session
setup 2.7–4.5 s, on an otherwise idle box (load 0.15 / 16 cores). Our per-page traffic is 338 KB up and
12 KB down, so the asymmetry lands entirely on the wave: ≈ **33 h** for the three populations here against
≈ **2 h** on the 2026-09-11 machine. `PADDLE_MEASUREMENTS.md` carries the full table.

*The machine is Paddle-only (Gustavo, 2026-09-15).* The 18 GB of Qwen weights under `/workspace/models`
were deleted and the vLLM template's services (`vllm`, `ray`, `model-ui`) stopped with their supervisor
units moved to `/root/removed-services-backup/` — reversible: copy a unit back, then `supervisorctl reread
&& supervisorctl update`. The instance's own management surface (`caddy`, `instance_portal`,
`tunnel_manager`, `cron`) is untouched, as its agent guide requires. Disk went 75% → **19% used (27 GB
free)**; GPU idle at 2 MiB of 32,607. `/workspace` is NOT a mounted volume here either: stop/start
preserves the container, recycle/destroy wipes it — including `/workspace/paddle-env`, so a recycled
instance needs the stack installed again (into its own virtualenv, per lesson 1). No customer page was sent
by any of this; the live proof used the synthetic fixture only.

### Lossless transfer tuning (2026-09-15, requested by Gustavo)

Gustavo selected the configured instance and then requested faster document transfers. Cell W's
`7897518` adds the optional connection setting `PADDLE_VAST_SSH_COMPRESSION=yes` (or `no`). Unset or
blank preserves the existing SSH configuration. The option applies when a new tunnel opens; an
already-running tunnel must complete its normal stop/attestation/tunnel-down lifecycle first.
The option changes only SSH transport. The receiver obtains the identical HTTP and PNG bytes; the
worker contract, OCR pins, image resolution, evidence hashes and cache keys are unchanged.
[OpenSSH documents compression of forwarded TCP data](https://man.openbsd.org/ssh).

The preliminary synthetic transfer experiment measured a shorter mean transfer with compression,
with substantial variation between trials. See the new measurements section for the sample, limits
and exact observations. This is not yet a measured improvement for the persistent HTTP wave.
The updated wave/vast targeted checks passed (123 tests); final branch proofs and the live SLICE
retention attestation are still required before W composes.

The earlier 33-hour projection covered a full set of populations. CTRL and U755 have already finished
their attempt records and are preserved. The current SLICE file has 80 documents / 626 pages; 46 pages
have prior successful evidence, 33 have prior refusals and 547 have never been attempted. The later
configuration A/B reads are separate work. Do not restart completed CTRL/U755 sessions for this tuning.
