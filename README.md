# Bank Statement → Markdown (Unlimited-OCR)

Converts a bank-statement PDF into one Markdown file by running each page through
`baidu/Unlimited-OCR` on an **OpenAI-compatible endpoint**. The OCR stage itself
does no math — it only transcribes. The downstream
[analysis layer](#analysis-layer--statement--metrics--mcalender-findings-gemini)
turns that markdown into structured metrics (daily average balance, deposits, NSF
counts) and MCA/lender findings.

## How it runs

The model runs on a GPU **elsewhere** — this machine is only the client. The
endpoint is policy-checked in code (`ocr/endpoint_policy.py`, OQ3 = ALLOWLIST):
a loopback or private-network endpoint is used by default; a remote endpoint
is refused unless you explicitly opt in (see below). There is exactly one
endpoint per process — a failing local server never silently falls back to a
remote one.

- **Local (default, $0):** your own GPU box, via transformers + PyTorch-ROCm
  behind a small OpenAI-compatible shim (`local_ocr_server.py`). Verified on
  an AMD **RX 7800 XT** (vLLM/SGLang are CUDA-only and Ollama/llama.cpp don't
  support this architecture, so transformers is the route on RDNA3). See
  [Serving locally on an AMD GPU](#serving-locally-on-an-amd-gpu-rx-7800-xt--rocm).
- **Remote (optional, PAID — never automatic):** a rented **RunPod** NVIDIA
  GPU serving `baidu/Unlimited-OCR` via vLLM's dedicated
  `vllm/vllm-openai:unlimited-ocr` image (exposes `/v1`). See
  [Optional PAID remote escape hatch](#optional-paid-remote-escape-hatch--never-automatic-runpod)
  below — it requires an explicit `OCR_REMOTE_OPT_IN` and is refused without it.

No OpenAI account or metered cost is involved for the local path; the `openai`
package just speaks the same wire format your server exposes.

## Setup (Python 3.12)

```bash
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Poppler must be installed (Windows: `C:\poppler-24.08.0\Library\bin`).

## Serving locally on an AMD GPU (RX 7800 XT / ROCm) — the default

Runs `baidu/Unlimited-OCR` on your own GPU — $0, no per-hour cost, and the
endpoint this project defaults to (`http://localhost:8000/v1` classifies as
`loopback`, allowed by the endpoint policy with no opt-in required).
`local_ocr_server.py` loads the model via its `trust_remote_code` `model.infer(...)`
and exposes the same `/v1/chat/completions` the client already speaks, so the CLI
and webapp work unchanged. Verified on an RX 7800 XT (gfx1101), ROCm 6.3/7.x,
Python 3.12–3.14, at ~23 s/page.

```bash
# one-time: add the GPU-serving deps on top of the client venv
.venv/bin/python -m pip install -r requirements-local.txt

# start the server (loads the model, then serves on http://localhost:8000/v1)
./serve_local.sh
```

Then, in another shell, point the client at it and run as usual:

```bash
export OCR_BASE_URL=http://localhost:8000/v1
export OCR_API_KEY=EMPTY
.venv/bin/python -m webapp.app          # or: .venv/bin/python parse.py <pdf> --out out.md
```

Notes:
- **transformers must be 4.x** (pinned in `requirements-local.txt`) — the model's
  remote code imports `is_torch_fx_available`, removed in transformers 5.x.
- `serve_local.sh` sets `HSA_OVERRIDE_GFX_VERSION=11.0.0` (the standard RDNA3
  desktop workaround) and `HF_HUB_DISABLE_XET=1`.
- **Live streaming + region boxes work.** The server calls `infer()` in
  `eval_mode` (non-streaming client) or taps its internal `TextStreamer`
  (streaming client) so the raw `<|det|>label [x0,y0,x1,y1]<|/det|>` region tags
  reach the client token-by-token — driving the webapp's live fill, colored box
  overlays, and inline check-image cropping. (`save_results` mode would instead
  strip those tags into a clean `result.md`, killing the boxes — so the server
  avoids it.)
- The vLLM-only request fields (`skip_special_tokens`, `vllm_xargs`) are accepted
  and mapped where meaningful (`ngram_size`→`no_repeat_ngram_size`,
  `window_size`→`ngram_window`) or ignored.
- **RDNA3 stability fix:** the server forces the math SDPA backend during
  inference. The vision encoder's `scaled_dot_product_attention` otherwise hits an
  experimental ROCm flash/mem-efficient kernel that faults with an HSA hardware
  exception on gfx1101 for larger image tensors. Math is always correct (slightly
  slower). Keep `image_size` at 640 (Gundam crop) — `image_size=1024` crashes even
  with the math backend.
- **DPI 300 is the tuned default** (`parse.py`/pipeline). On dense check-detail
  tables, 200→300 measurably recovers amounts the model dropped at 200; 400 is
  *worse* (oversampling degrades the crop tiling). The prompt stays `Free OCR.` —
  the `<image>\n<|grounding|>…` markdown prompts return empty output on this model.

## Optional PAID remote escape hatch — never automatic (RunPod)

RunPod is documented ONLY as an explicit, deliberate, opt-in fallback for when
no local GPU is available — never a production default and never something a
failed local rung falls back to silently (OQ6 / OQ3). `ocr/endpoint_policy.py`
classifies `*.runpod.net` (and every other public host) as `remote`, which the
client refuses before building anything or sending a single byte UNLESS
`OCR_REMOTE_OPT_IN` is set to the exact literal `I_ACCEPT_REMOTE_PAID_OCR`:

```bash
export OCR_BASE_URL="https://<pod-id>-8000.proxy.runpod.net/v1"
export OCR_REMOTE_OPT_IN="I_ACCEPT_REMOTE_PAID_OCR"   # required for any remote host; omit it and the client refuses
```

The run's telemetry records `endpoint_class=remote` and `remote_opt_in=true`
whenever this path is used, so a remote/paid read is always evidenced, never
inferred. Requires the dedicated image (the architecture isn't in a stable
vLLM pip release):

```
Container image:        vllm/vllm-openai:unlimited-ocr
Container start command: baidu/Unlimited-OCR --host 0.0.0.0 --port 8000 --trust-remote-code \
                          --logits_processors vllm.model_executor.models.unlimited_ocr:NGramPerReqLogitsProcessor \
                          --no-enable-prefix-caching --mm-processor-cache-gb 0
Environment variables:  HF_HUB_DISABLE_XET=1
Container disk:         60GB
Expose HTTP ports:      8000
GPU:                    any card with >=8GB VRAM (BF16)
```

## Configure the endpoint

```bash
export OCR_BASE_URL="http://localhost:8000/v1"                    # default: the local server, above
export OCR_MODEL="baidu/Unlimited-OCR"                            # default
export OCR_API_KEY="EMPTY"                                        # or the token your server expects
# optional: OCR_TIMEOUT (default 120), OCR_RETRIES (default 3),
#           OCR_NGRAM_SIZE (default 35), OCR_WINDOW_SIZE (default 128)
# a remote host (e.g. RunPod, above) additionally requires OCR_REMOTE_OPT_IN
```

`OCR_WINDOW_SIZE` should be raised (e.g. 1024) if you send multi-page/whole-document
requests instead of single pages.

## Usage

```bash
.venv/Scripts/python.exe parse.py "Bank Statements/Chase/Chase Salomon January.pdf" --out output/chase.md
# flags: --out FILE (else stdout), --dpi N (default 300), --model NAME (override)
# offline (native/local text) only by default; add --visual to allow the
# local $0 OCR rung when the offline ladder cannot read the document —
# probed and endpoint-checked before anything is sent.
```

Output: one `.md` with a provenance comment header and pages separated by
`--- Page N ---`. The model's own `<|det|>...<|/det|>` region-annotation tags are
stripped automatically, leaving clean text and HTML tables.

## Local web frontend

A dark, 4-panel document viewer (original page images | markdown source |
rendered markdown | analysis metrics) with a toolbar to upload PDFs, switch between documents, and
download results. Default (local server, above):

```powershell
.venv\Scripts\python.exe -m webapp.app
```

Using the optional PAID RunPod escape hatch instead — pass the current pod id
and `run.ps1` derives the endpoint + key for you, but the endpoint policy
still refuses it without the opt-in below:

```powershell
$env:OCR_REMOTE_OPT_IN = "I_ACCEPT_REMOTE_PAID_OCR"
.\run.ps1 -PodId jy39vysntpffa0
```

Or set the env vars yourself and run it directly with the venv Python (note:
plain `python` is the wrong interpreter — use the venv one so the deps resolve):

```powershell
$env:OCR_BASE_URL = "https://<pod-id>-8000.proxy.runpod.net/v1"
$env:OCR_API_KEY  = "sk-<pod-id>"
$env:OCR_REMOTE_OPT_IN = "I_ACCEPT_REMOTE_PAID_OCR"
.venv\Scripts\python.exe -m webapp.app
```

Then open `http://localhost:5000`. Uses the same `OCR_*` environment variables as
the CLI.

## Analysis layer — statement → metrics + MCA/lender findings (Gemini)

The `analysis/` package turns the OCR markdown into structured underwriting data.
It's built on **separation of concerns**: an LLM (Google **Gemini**, cheap
`gemini-3.5-flash-lite`) only transcribes the statement into a normalized ledger;
all math and detection is deterministic Python. Stages:

1. **Extract** (`extract.py`) — markdown → `Statement` via Gemini structured
   outputs (Pydantic `response_schema`). Captures line items *and* the bank's own
   printed summary block (totals, counts, printed average balance).
2. **Reconcile** (`reconcile.py`) — `beginning + Σamounts == ending`, running-
   balance continuity, and **line-item coverage vs the bank's stated totals**.
   Catches OCR/extraction errors before any number is trusted. A statement that
   fails reconciliation is automatically re-extracted with the stronger
   `gemini-3.5-flash` (you pay flash-lite prices for the clean majority).
3. **Metrics** (`metrics.py`) — daily average balance (from dated running
   balances, carrying forward across no-activity days), or the bank's printed
   average when line items are incomplete; deposits/withdrawals, NSF count,
   negative days.
4. **Detect** (`detect.py`) — MCA/lender detection: a known-funder dictionary
   plus recurring fixed-debit pattern detection (the daily/weekly remittance
   signature), each returning the evidence transactions.

```bash
# one-time: deps + API key (key lives in a gitignored .env, never in code)
.venv/bin/python -m pip install -r requirements-analysis.txt
echo 'GEMINI_API_KEY=your-key-here' > .env

# analyze one OCR'd statement
.venv/bin/python analyze.py output/ace.md              # human-readable report
.venv/bin/python analyze.py output/ace.md --json out.json

# batch-triage a whole folder into a CSV (one row per statement)
.venv/bin/python batch.py output/ --out triage.csv     # folder of .md
OCR_BASE_URL=http://localhost:8000/v1 OCR_API_KEY=EMPTY \
    .venv/bin/python batch.py "Bank Statements/" --out triage.csv   # PDFs (OCR + analyze)
```

The batch CSV carries the key underwriting figures per statement plus a
`needs_review` flag driven by whether the bank's own summary reconciles — clean
statements flow through, only the questionable ones get human eyes. Small-bank /
image statements (where per-transaction detail is incomplete) still yield
trustworthy figures from the bank's printed summary, which reconciliation validates.

Tune via env: `GEMINI_MODEL` — the ONE hosted extraction model, and the hosted
branch runs only behind the operator opt-in documented in `analysis/pipeline.py`
(Phase 2.2, P22-FENCE; Ruling A). `GEMINI_ESCALATION_MODEL` is retained for
settings-key stability only and is no longer read: the reconciliation-driven
re-extraction with a second model was removed (ruling R9). Withholding divides by
True revenue (`WITHHOLDING_DENOMINATOR_MODE=true_revenue`: verified plus counted
credits) by default since the owner's ruling of 2026-10-02 (the underwriter's
Q7); an unset or unknown value reads as that default. Set
`WITHHOLDING_DENOMINATOR_MODE=legacy_eligible_deposits` for legacy eligible
deposits (deposits less lender funding, the default until then) or
`WITHHOLDING_DENOMINATOR_MODE=verified_revenue` for verified classified revenue;
in either revenue mode `eligible_deposits` carries the selected denominator, and
the legacy figure stays in `legacy_eligible_deposits` on every statement. An
analysis stored without a mode keeps the legacy basis it was made under. The withholding numerator is the confirmed lender debits paid plus the
funder payments returned unpaid (the owner's ruling of 2026-10-02, the underwriter's Q5): a bounced payment leaves
"paid to lenders" but stays in the rate. Zelle deposits follow the Settings
choice "Mark Zelle Payments as True Revenue" (the owner's amendment of
2026-10-06 to the underwriter's Q3): Yes, the default, counts them in True
revenue as the rules read a person-to-person credit (the holder's own name and
one sender's repeated round sums held); No makes them non-revenue
(`zelle_excluded`). The analysis stores both readings, so the choice applies to
every saved analysis at once; `analyze.py` and `batch.py` take
`--zelle-true-revenue {yes,no}` (default yes) and read no webapp setting.
Extend maintained lender, candidate,
insurance, operating-revenue, and exclusion aliases in
`analysis/classification_registry.py`.

Transaction categories, lender/insurance precedence, contribution flags, the
revenue tiers and their reason codes (True and Verified revenue), and the
eligible-deposit denominator are defined in
[`docs/transaction-classification.md`](docs/transaction-classification.md); the
True revenue design is
[`docs/superpowers/specs/2026-09-28-true-revenue-design.md`](docs/superpowers/specs/2026-09-28-true-revenue-design.md).

## Tests

```bash
.venv/Scripts/python.exe -m pytest            # fast unit tests (network mocked)
OCR_BASE_URL=... .venv/Scripts/python.exe -m pytest -m live   # real-endpoint smoke
```

## Discovery runner — intake and outcome over an arbitrary corpus

`python -m discovery` points the merged platform at a directory of unknown
PDFs and reports what happened: intake profile, dedup, which parser claimed
each document and with what score, which parsers *almost* claimed it, the
outcome class, and the failure taxonomy — plus rollups (deterministic
coverage, bank/layout clusters, ranked unknown-layout groups, parser-claim vs
folder-label, ambiguity clusters, cache stats).

```bash
.venv/Scripts/python.exe -m discovery --dry-run        # the pinned 109. The gate.
.venv/Scripts/python.exe -m discovery --profile-only   # tranche 0: intake only
.venv/Scripts/python.exe -m discovery --digital        # tranche 1: offline rungs
.venv/Scripts/python.exe -m discovery --scanned        # tranche 2: + local Tesseract
.venv/Scripts/python.exe -m discovery --scanned-visual # tranche 3: + the visual rung
.venv/Scripts/python.exe -m discovery --dry-run --no-cache --limit 20
```

It owns no routing, no parsers and no financial logic: it consumes O-1
preflight profiles, the production intake ladder, D-3's cache, R-3's registry
dispatch and H-3 telemetry. **Offline by construction in tranches 0–2** —
`deterministic` parse mode makes the LLM branch unreachable and the visual-OCR
rung is disabled, so the model client module is never even imported (asserted
by test). Tranche 2 adds only the local Tesseract binary; tranche 3
(`--scanned-visual`, below) adds the local visual-OCR rung and nothing else.

Documents a tranche cannot read are **recorded, never skipped**: a scanned PDF
in tranche 1 is `deferred_scanned` and appears in the report as work not done.

### Tranche 3 — the visual-OCR rung (`--scanned-visual`)

`--scanned-visual` is `--scanned` with the intake ladder's last rung enabled:
the **local** `baidu/Unlimited-OCR` server on your own GPU (see *Local GPU*
above). No paid vendor is reachable from any discovery mode, and the extraction
LLM stays unreachable here too — the rung reads pixels into markdown, it does
not extract. Policy stays offline-first, and a document reaches the GPU in
exactly two situations:

| | When | Outcome |
|---|---|---|
| **recovery** | the offline rungs produced nothing at all (`deferred_visual_ocr` in tranche 2) | the visual read becomes the text of record |
| **upgrade** | the offline read came from local Tesseract and **no parser claimed it** | the visual read is adopted only if it claims; otherwise the Tesseract read stays of record |

An unclaimed *native-text* document is never escalated: that is a layout
problem, and re-reading perfect text with a GPU cannot invent a parser.
`--no-visual-escalation` restricts the mode to recovery only.

```bash
python local_ocr_server.py &                          # or point OCR_BASE_URL elsewhere
.venv/Scripts/python.exe -m discovery --scanned-visual
.venv/Scripts/python.exe -m discovery --scanned-visual --no-visual-escalation
OCR_BASE_URL=http://localhost:8000/v1 .venv/Scripts/python.exe -m pytest -m live
```

**Availability is checked before the run, not during it.** The mode probes
`GET /v1/models` up front (no GPU time, no image sent) and refuses to start,
with an actionable message and exit code 2, if the endpoint is unreachable or
does not serve the configured `OCR_MODEL` — a batch of thousands must not
discover that on document 1. If the server dies **mid-run**, that document
fails closed (`failed` / `ocr_failed`, with the exception class recorded) and
the run continues; a failed read is never cached.

Each visual read goes through the D-3 artifact cache in its own partition (the
ladder capability flags and every visual service knob — model, base URL, dpi,
fallback dpi, ngram/window — are cache-key material), is assessed for O-3
truncation exactly like every other rung, and is recorded by H-3 with its own
`visual_ocr` stage timing, `source.path = "visual"`, the model id and the page
count. Local infrastructure bills no vendor, so the cost estimate names the
model as unpriced rather than inventing a rate.

The deferral taxonomy does not soften: a document the visual rung **also**
cannot serve stops being `deferred` and becomes an explicit terminal `failed`.
`rows.csv` gains `visual_rung` (`recovered` / `upgraded` / `no_upgrade` /
`failed` / `not_attempted`) and `cache_visual`, and the report ranks them.

Every run first verifies the corpus root against the frozen archive baseline
(3,768 files / 3,615 PDFs / 996,080,803 bytes) and refuses to proceed if it has
moved — tranche numbers are only comparable if every tranche measured the same
corpus. `--dry-run` checks the pinned 109 instead, so it works in a clean
checkout. `--skip-baseline` is for scoped runs whose numbers are not
tranche-comparable.

Output goes to the gitignored `discovery_reports/<run_id>/`: `report.txt`,
`summary.json`, `rows.csv`, `hash_map.csv`, and `telemetry.jsonl`. Two
artifacts, two audiences — the telemetry records carry hashes and codes only
(the H-3 invariant), while the report carries relative paths and folder labels
for human adjudication, with account identifiers masked to last-4 and no
transaction-level detail anywhere.

## Telemetry — what happened to each statement, and what it cost

One write-only record per statement per run: content hash, intake path taken,
parser id and detection score (including the near-miss scores of parsers that
almost claimed it), dispatch outcome, per-stage timings and cache hit/miss,
truncated-page flags, model calls, and an outcome class
(`validated` / `review` / `withheld` / `failed`). It is a side-band: **no
analysis output changes because telemetry is on**, proven by test and by the
corpus gate.

It is **on by default** on both paths. The webapp writes to the SQLite store
(schema v4); `batch.py` writes JSON Lines to `telemetry_runs/<run_id>.jsonl`
(gitignored) or wherever `--telemetry FILE` points.

```bash
.venv/Scripts/python.exe batch.py "Bank Statements" --out triage.csv
.venv/Scripts/python.exe -m telemetry.report --jsonl telemetry_runs/<run_id>.jsonl
.venv/Scripts/python.exe -m telemetry.report --sqlite webapp_data       # same report
.venv/Scripts/python.exe -m telemetry.report --jsonl … --by parser      # breakdowns
.venv/Scripts/python.exe -m telemetry.report --jsonl … --diagnostics    # W3-2: withheld failure-class rollup
.venv/Scripts/python.exe -m telemetry.report --jsonl … --by diagnostic_class
TELEMETRY_DISABLED=1 .venv/Scripts/python.exe batch.py …                # kill switch
```

`TELEMETRY_DISABLED=1` (also `true`/`yes`/`on`) swaps in a null sink everywhere,
webapp included. Nothing else changes.

**Records carry no customer data, by design and by test:** hashes, registry
ids, enum codes, counts and timings only — never account numbers, amounts,
transaction text, statement dates, the extracted bank label, or **filenames**
(customer names live in paths). Exceptions are recorded by class name, never by
message. That invariant is what makes always-on telemetry safe; see
`docs/moneythumb-replacement/H3_SCHEMA.md` for the full schema and the
sensitivity tests.

Telemetry is append-only (the table carries the same UPDATE/DELETE triggers as
the audit log). There is no expiry path yet — retention is a later decision.

## MoneyThumb comparison harness

Offline, re-runnable comparison of the six MoneyThumb benchmark result sets
against our pipeline, the original statement evidence, and the audited
expectation CSVs. MoneyThumb is never treated as automatic ground truth:
every compared field is classified into one of eight outcomes
(`BOTH_MATCH_EXPECTED | OUR_SYSTEM_CORRECT | MONEYTHUMB_CORRECT |
BOTH_INCORRECT | DIFFERENT_DEFINITION | SOURCE_CONTRADICTION |
INSUFFICIENT_EVIDENCE | UNRESOLVED`) with evidence pointers, and the rollup
proves every MoneyThumb JSON field was either compared, skipped by a
documented FIELD_MAPPING verdict, or recorded as a capability finding.

```bash
# One command, fully offline (no OCR endpoint, no Gemini, no network).
# --mt-results points at the read-only moneythumbResults/ directory
# (default: <repo>/moneythumbResults).
python -m benchmark --mt-results "path/to/moneythumbResults"

# Optional: --corpus "Bank Statements" --cache tests/corpus_cache \
#           --out benchmark_reports --sets wmb_may klr_may
```

Outputs (written to `benchmark_reports/`, gitignored, never committed):
per-set `<set>/report.json`, cross-set `rollup.json`, `summary.csv`, and a
human-readable `SUMMARY.md` with an explicit "for Ocean ruling" section.
All account numbers in every report are masked to last-4; reports never
contain full ledgers or holder identities. The harness verifies the
manifest's PDF SHA-256 hashes before running and stops on any mismatch.

Harness unit tests (synthetic fixtures only):

```bash
python -m pytest tests/test_benchmark_harness.py -q
```

## Corpus gate — required before merge

The 106-of-109 guarantee is not a claim in a document; it is re-proved on
demand. The gate re-runs both independent forensic oracles over every corpus
statement and fails red on any drift from the committed audits
(`docs/adb-audit-results.csv`, `docs/balance-metrics-audit-results.csv`).

```bash
.venv/Scripts/python.exe corpus_gate.py                      # exit 1 on any drift
.venv/Scripts/python.exe corpus_gate.py --json report.json   # machine-readable report
.venv/Scripts/python.exe corpus_gate.py --corpus <path>      # audit another checkout's root
.venv/Scripts/python.exe -m pytest -m corpus                 # the same gate via pytest
```

### What the gate is scoped to

The gate audits the **pinned manifest** — the 109 corpus-relative paths recorded
in the committed audit CSVs — not "whatever PDFs the directory holds". The
corpus root doubles as the landing zone for untracked discovery material
(`.gitignore` carries `Bank Statements/**`, so nothing untracked under that root
can be committed by accident), which makes "every PDF under the root is pinned"
a property the tree is not meant to have.

The trade is deliberate and narrow:

- **Kept, and tightened.** Every pinned path must exist on disk, hash-match its
  pin, and carry a row in *both* audits; the two audits must pin the same 109
  paths. A statement that is deleted, renamed, or edited is red. Committed OCR
  artifacts are checked against the manifest, so an artifact for an unpinned
  document is still an orphan error.
- **Given up.** The gate no longer asserts that the corpus root contains nothing
  else. Instead it counts what else is there and says so — `foreign_files`
  reports `N non-corpus PDFs present — ignored (discovery archive)` with a
  folder count and no file names (unpinned documents under this root are
  sensitive source data). That check is informational and can never fail the run.

Adding a statement to the validated corpus is therefore an explicit act: the
audit CSVs must be regenerated (below) and the file added with `git add -f`.

Measured runtime: **4m32s–6m19s** on a Windows dev box (Python 3.14), across the
script and `pytest -m corpus` forms. Both oracles re-parse every statement
independently, which is the point — they are not allowed to share a parse.

**Run this before merging anything that touches parsing, reconciliation, ADB,
balance metrics, serialization, the API, dashboard bindings, or exports.** It is
also wired to run on every pull request
(`.github/workflows/corpus-gate.yml`). The default `pytest` run deselects it, so
day-to-day testing stays at about a minute.

That workflow installs `poppler-utils` and `tesseract-ocr` on the runner before
the suite: the gate itself needs neither, but the default suite exercises the
real local OCR ladder (poppler page counts, two live-OCR'd scanned fixtures).
Hosted-runner acquisition failures ("The job was not acquired by Runner of type
hosted") are a GitHub-side transient — re-run the job and check
[githubstatus.com](https://www.githubstatus.com); nothing in this repository
causes or fixes them. See `docs/moneythumb-replacement/CI1_FINDINGS.md`.

What it checks, in order. Every one of them fails the run except the two marked
informational (`foreign_files`, `exclusions`), which report and never fail:

| Check | Guarantee |
|---|---|
| `inventory` | All 109 pinned corpus PDFs are on disk and audited by both oracles, which pin the same paths. Nothing removed or renamed without an audit row. |
| `foreign_files` | Counts PDFs under the corpus root that are not pinned and reports them as ignored. **Informational — never fails the run.** |
| `source_integrity` | Every pinned PDF matches its pinned SHA-256, so the documents themselves have not changed. |
| `balance_audit` | Every audited opening/ending/highest/lowest value reproduces across backend, API, dashboard binding, CSV, XLSX, and package surfaces — compared field by field, not just by status. |
| `adb_audit` | Every audited ADB field reproduces across backend, API, and dashboard-package surfaces. |
| `balance_outcomes` / `adb_outcomes` | Still 106 PASS and 3 WITHHELD, and the withheld set is still the same three statements. A source contradiction cannot quietly become a pass. |
| `ocr_coverage` | All 109 statements resolved offline: 103 from native text, 6 from committed OCR artifacts. |
| `exclusions` | Named, counted exclusions. Currently zero. |
| `oracle_independence` | The audit scripts still import no production financial mathematics, so they remain an independent check rather than a mirror. |

The gate is offline by construction: no OCR endpoint, no Gemini, no network, and
no `tesseract` binary. The six image-only statements are served from committed
OCR artifacts keyed by the SHA-256 of their source PDF — see
[`tests/corpus_cache/README.md`](tests/corpus_cache/README.md). A scanned
statement with no artifact is a failure, never a silent skip.

The gate **consumes** the audit CSVs and never rewrites them. Regenerating the
truth set is a separate, deliberate act:

```bash
.venv/Scripts/python.exe adb_forensic_audit.py "Bank Statements" --ocr-cache tests/corpus_cache
.venv/Scripts/python.exe balance_forensic_audit.py "Bank Statements" --ocr-cache tests/corpus_cache
```

### A note on line endings

`.gitattributes` marks PDFs binary. Do not remove it. With `core.autocrlf=true`
git rewrites any PDF whose first 8000 bytes contain no NUL — which includes
statements with ASCII85 image streams — making the corpus byte-different per
platform and the pinned hashes unreproducible.
