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
* The remote host's `/venv/main` already has `paddleocr==3.7.0`, `paddlepaddle-gpu`,
  Pillow and numpy installed, and the two PP-OCRv5 models cached
  (`PP-OCRv5_server_det`, `en_PP-OCRv5_mobile_rec`). `tools/paddle_vast.py check`
  verifies this without starting anything.
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

**Rasters.** Under the research partition the PNG of every page sent is kept at
`<research dir>/rasters/<content sha>/pNNNN.png`, and only when its sha256 reproduces the
`raster_sha256` the immutable evidence already records for that page — so a retained image is
provably the one the worker saw. Production partitions keep `raster_sha256` and no file.
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
