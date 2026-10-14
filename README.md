# Capital Infusion: bank statement analysis

Reads business bank-statement PDFs and produces what an MCA underwriter needs: balances, the calendar-day
average daily balance, NSF days, True revenue, confirmed and potential lenders, alternative positions, the
withholding rate and active positions, for one statement or a package of several months. All of it is
deterministic Python on this machine: no model is called, scanned statements are read by local Tesseract,
and no statement data leaves the machine. It fails closed: a statement is published only when its own printed
figures prove the reading; otherwise it is withheld or sent to review with the reason.

The old model-based OCR and extraction paths are retired and are being removed from the tree.

## How it works

| Stage | What happens | Where |
|---|---|---|
| Intake | Upload checks (100 MB, 25 files, 500 pages, a `%PDF-` header, no encrypted PDF), the whole batch before any job; preflight profile and content hash | `webapp/app.py`, `ocr/inspect.py` |
| Native text | PyMuPDF reads the PDF's own text: six bank-specific readers, a printed-rows reader, then generic text | `ocr/pipeline.py` (`parse_statement`), `ocr/native_text.py` |
| Scans | When the native readers return nothing (a scan, or too little text), the pages are rendered at 200 dpi, 8 at a time, and read by local Tesseract (`--psm 6`) one page at a time; under 200 characters is no read. A step past 120 s, a document past an hour, or a host failure (a full, failing or read-only disk, a disk quota or memory run out while pages are rendered or read; a tesseract that cannot start or is killed) fails the job and caches nothing | `ocr/local_tesseract.py`, `ocr/rasterize.py` |
| Dispatch | 84 registered per-bank parsers score the text; exactly one must claim it. Ambiguous, unclaimed or a parser crash publishes nothing | `analysis/parser_registry.py`, `analysis/parser_registry_entries.py`, `analysis/pipeline.py` |
| Reconciliation | Opening + postings = ending, running-balance continuity, the bank's printed summary; quality and integrity gates | `analysis/reconcile.py`, `analysis/pipeline.py` |
| Multi-account | A document with several accounts is split on its printed account sections; each is validated on its own | `analysis/multi_account.py`, `analysis/pipeline.py` (`analyze_document`) |
| ADB, NSF, metrics | Calendar-day ADB over the printed period (withheld when the ledger is unprovable); negative-ending days, printed days by default; deposits, withdrawals, withholding | `analysis/adb.py`, `analysis/nsf_days.py`, `analysis/metrics.py` |
| Classification | Every posting gets a revenue tier (verified, counted and flagged, held for review, non-revenue), a lender state or a flag group | `analysis/transaction_classifier.py`, `analysis/true_revenue.py`, `analysis/revenue.py` |
| Lenders | Registry matching and evidence, payment changes, active positions, 12 flag groups | `analysis/classification_registry.py`, `analysis/payee_matcher.py`, `analysis/detect.py`, `analysis/flag_groups.py`, `analysis/lender_payment_changes.py`, `analysis/active_positions.py` |
| Display layer | Steps run on a copy when a result is served (the Zelle reading, the NSF basis, hidden flag groups, revenue figures, active positions), so a Settings change needs no re-analysis | `analysis/zelle_view.py`, `analysis/nsf_days.py`, `analysis/flagged_view.py`, `analysis/revenue_view.py`, `analysis/active_positions.py` |
| Web app | Flask on waitress (16 threads), one worker thread, SQLite store, an artifact cache keyed by content hash, packages, re-analysis and review decisions | `webapp/app.py`, `webapp/worker.py`, `webapp/storage.py`, `webapp/artifact_cache.py`, `webapp/reanalysis.py` |
| Dashboard | New analysis, the results (Statements, Packages, Revenue review) and Settings; downloads and copied memos | `webapp/templates/index.html`, `webapp/static/app.js` |

Each statement ends as `validated`, `review`, `withheld`, `refused` or `failed`. A package groups several
statements (months, accounts): duplicates and superseded statements are found and the package-level passes run
(returned deposits across statements, own-account transfers).

## Quick start

**1. Python and packages.** Use Python 3.12, the version CI uses.

```powershell
# Windows PowerShell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-analysis.txt
```

```bash
# bash (Linux, macOS)
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-analysis.txt
```

Both files are needed. They still list two packages for the retired code: `google-genai`
(`requirements-analysis.txt`), which is imported at load time, and `openai` (`requirements.txt`), which is
not. No API key is needed, whatever the header of `requirements-analysis.txt` says. Every command below assumes
the venv is active.

**2. System tools.**

- **Poppler: required.** Every upload's page count runs `pdfinfo`, and page previews use it; without it every
  PDF is refused as unreadable. On Windows `pdfinfo.exe` must be in `C:\poppler-24.08.0\Library\bin`, or set
  `POPPLER_PATH` to the folder that holds it (PATH is not searched on Windows). Linux:
  `sudo apt-get install poppler-utils`; macOS: `brew install poppler`.
- **Tesseract: for scans only.** Found on PATH as `tesseract`, with English data (`eng.traineddata`). Windows:
  install it and add `C:\Program Files\Tesseract-OCR` to PATH. Linux:
  `sudo apt-get install tesseract-ocr tesseract-ocr-eng`. Without it a scanned statement fails closed
  ("native PDF text unavailable").
- **Node: optional.** Only the dashboard script tests use `node`; they skip without it.

**3. Run the web app** from the repository root.

```powershell
.\run.ps1                           # http://127.0.0.1:5000, the default data directory
.\run.ps1 -Port 5050 -DataDir D:\statement-data
python -m webapp.app                # the same app without the launcher
```

```bash
python -m webapp.app
WEBAPP_PORT=5050 WEBAPP_DATA_DIR=/srv/statement-data python -m webapp.app
```

Then open `http://127.0.0.1:5000`. There is **no login**: anyone who can reach the port can read every
statement, so it binds `127.0.0.1` unless `WEBAPP_HOST` says otherwise; `run.ps1 -BindAll` is a deliberate
choice for a trusted network only. On restart, unfinished jobs are marked `interrupted`, never resumed silently.

**Data directory.** The default is `~/.local/share/bank-statement-analysis/phase31-private/webapp_data`
(`%USERPROFILE%\.local\share\...` on Windows). `WEBAPP_DATA_DIR` sets the folder itself. It must be an absolute
path outside the checkout, symlinks included, or the app refuses to start. It holds `webapp.db` (SQLite: jobs,
documents, packages, review decisions, the audit log, the artifact cache, telemetry), the uploaded PDFs as
`<SHA-256 in upper-case hex>.pdf`, `artifacts/` and `settings.json`. Treat it as customer data. Nothing in it is
ever deleted, so watch its volume: uploads stop at `WEBAPP_MIN_FREE_MB`, and if the volume cannot be written when the
app starts (full or read-only) the app starts read-only: saved statements can be viewed, everything else is refused
until space is freed and the app is restarted.

## Parse modes

The upload page offers **Auto** (the default) and **Deterministic only**. Both read native text first, then
local Tesseract, and both run only the deterministic parsers, so today they give the same results; Auto labels
its output `auto` and is cached separately. A statement no parser claims ends as "no deterministic parser
matched this statement" in both. Nothing falls back to hosted extraction (Ruling A).

The page still shows a **Force visual OCR** checkbox, and some messages (the scan-failure message, the top-bar
hint) still mention visual OCR. That is the retired model path: leave the box unticked. A forced job skips
native text and is refused, so nothing is read.

## Command-line tools

```bash
python parse.py statement.pdf --out statement.md     # native text to Markdown (--html for a page)
python analyze.py statement.md                       # report, one per account
python analyze.py statement.md --json report.json
python batch.py <folder> --out triage.csv            # .md and .pdf files, one CSV row per statement
python -m telemetry.report --jsonl telemetry_runs/<run_id>.jsonl   # --by parser, --diagnostics, --json
python -m discovery --dry-run                        # intake and outcome over the pinned 109, offline
python -m benchmark --mt-results <moneythumbResults dir>           # MoneyThumb comparison, offline
```

- `parse.py` and `batch.py` read native text only (no Tesseract), so use the web app for scans. Ignore every
  option their `--help` describes as visual OCR or a model, and the hint in their no-text error to rerun with
  one: those are the retired paths.
- `analyze.py` and `batch.py` take `--zelle-true-revenue {yes,no}` (default yes) and read no web app setting.
- `analyze.py` reads Markdown only: given a PDF, it prints one error line and exits 2 (run `parse.py` first, or
  `batch.py` on the PDF).
- `batch.py` opens `--out` before it reads the first statement and writes each row as its statement finishes: a
  path it cannot write fails at once, and a stopped run keeps the finished rows and prints `INCOMPLETE: k of n files
  analysed` on stderr.
- Without `--out`, the three tools write UTF-8 to stdout, as their files are; `batch.py`'s stdout CSV is the
  `--out` file byte for byte.
- `batch.py` writes one telemetry record per statement to `telemetry_runs/<run_id>.jsonl` (or `--telemetry FILE`).
  `python -m telemetry.report --sqlite <data directory>` reads the web app's records instead.
- `python -m discovery` also runs `--profile-only` (intake), `--digital` (offline rungs) or `--scanned` (plus
  local Tesseract) over `--root`, after checking it against the frozen archive baseline (`--skip-baseline` for
  scoped runs). Ignore its retired `--scanned-*` and `--research-*` modes. Its cache is the web app's data
  directory unless you pass `--no-cache`. Reports go to the gitignored `discovery_reports/<run_id>/`.
- The benchmark verifies its manifest's PDF hashes first and writes masked reports to `benchmark_reports/`.

## Tests

```bash
python -m pip install -r requirements-dev.txt   # both runtime files plus the test-only packages
python -m pytest                                # the default suite
python -m pytest -m corpus                      # the 34 corpus tests, the gate among them
```

- `requirements-dev.txt` adds pytest, `jsonschema`, `pypdfium2` and `numpy` to the two runtime files. The last
  three are needed only because the suite still imports retired code (`vlm/`). Without them 35 test files fail to
  collect and pytest stops before running any test (exit 2). They go away with the removal.
- `pytest.ini` deselects the `live` and `corpus` markers. The `live` tests in `tests/test_live_smoke.py` and
  `tests/test_paddle_live.py` belong to retired endpoints: do not run them. The one local `live` check is the
  Tesseract drift test: `python -m pytest -m live tests/test_new_statement_corpus.py`.
- **Known failures** (after the audit fixes of 2026-10-13, Windows, Python 3.14): 14 failed, 25,350 passed,
  54 skipped, 39 deselected, in about 15 minutes. Twelve are Windows environment artefacts: 8 need the symlink
  privilege (`WinError 1314`), 3 check POSIX permission bits, 1 is a text-encoding mismatch. Two are guard tests
  that trip on the retired visual-pair code and wait for its removal:
  `test_no_statement_hardcodes::test_no_literal_account_numbers_in_ocr` (the two model revision pins in
  `ocr/visual_pair_config.py`) and `test_stated_counts::test_the_observer_is_not_wired_into_any_production_module`
  (a confidence label in `webapp/worker.py`). Any other failure is new.

## Corpus gate (required before merge)

```bash
python corpus_gate.py                      # exit 0 green, 1 red (about 17 minutes on Windows)
python corpus_gate.py --json report.json   # plus a machine-readable report
python corpus_gate.py --corpus <path>      # the same gate against another checkout's corpus root
```

The gate re-runs the two independent forensic oracles (`adb_forensic_audit.py`, `balance_forensic_audit.py`)
over the 109 pinned corpus PDFs and compares them, field by field, with the committed audits
(`docs/adb-audit-results.csv`, `docs/balance-metrics-audit-results.csv`): 105 pass, 3 withheld (the same three
proven source contradictions) and 1 pinned refusal. It also holds each document's published outcome, ADB
basis, currency and currency source to pinned values. Checks, in order: `inventory`, `foreign_files`
(informational), `source_integrity`, `balance_audit`, `adb_audit`, `balance_outcomes`, `adb_outcomes`,
`outcome_classes`, `adb_doctrine`, `currency`, `currency_source`, `ocr_coverage`, `exclusions` (informational),
`oracle_independence`.

- It is offline: no network, no model, no `tesseract`. The six image-only statements are served from committed
  OCR artifacts keyed by the SHA-256 of their PDF ([`tests/corpus_cache/README.md`](tests/corpus_cache/README.md)).
- It audits the pinned manifest, not every PDF under `Bank Statements/` (`.gitignore` ignores
  `Bank Statements/**`); other PDFs there are counted, never named. Adding a statement means regenerating the
  audits and `git add -f`.
- Run it locally before merging anything that touches parsing, reconciliation, ADB, balance metrics,
  serialization, the API, dashboard bindings or exports. CI (`.github/workflows/corpus-gate.yml`, Ubuntu 24.04,
  Python 3.12) runs on every pull request and every push to `main`: it checks that the shipped entry points import
  with the two runtime files alone, installs `requirements-dev.txt`, runs the suite, and runs the gate whether or
  not the suite passed (the job fails if either fails). Nothing makes a merge wait for it: GitHub's branch
  protection is not available on this repository's plan. Until the visual-pair code is removed, the suite step is
  expected to fail on the two guard tests named under Tests.
- The gate never rewrites the audits. Regenerating the truth set is a separate, deliberate act:
  `python adb_forensic_audit.py "Bank Statements" --ocr-cache tests/corpus_cache`, then the same with
  `balance_forensic_audit.py`. Both read every PDF under the path they are given, not the pinned manifest, and
  overwrite the committed audit CSVs and reports under `docs/`. Run them only on a folder that holds exactly the
  109 pinned PDFs (a fresh clone, where `Bank Statements/` holds only tracked files), and check that both CSVs
  still hold 109 rows before committing.
- `.gitattributes` marks PDFs binary and the committed OCR artifacts `-text`. Do not remove it: with
  `core.autocrlf=true` git would rewrite some PDFs and the pinned hashes would stop reproducing.

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `WEBAPP_HOST` | `127.0.0.1` | Bind address. Beyond loopback it exposes an app with no login. |
| `WEBAPP_PORT` | `5000` | Port. |
| `WEBAPP_DATA_DIR` | unset | The data directory; absolute and outside the checkout. |
| `WEBAPP_MIN_FREE_MB` | `256` | Free space the data volume keeps: an upload or a Re-analyze that would leave less is refused (507) before anything is written. `0` turns it off; a value that is not a whole number falls back to the default. |
| `VISUAL_PAIR_PRIVATE_ROOT` | `~/.local/share/bank-statement-analysis/phase31-private` | Root of the default data directory (`<root>/webapp_data`). The name is a leftover. |
| `POPPLER_PATH` | `C:\poppler-24.08.0\Library\bin` | Windows only: the folder holding `pdfinfo.exe`. Set it in the shell: `run.ps1` checks the shell's value, not `.env`. |
| `WITHHOLDING_DENOMINATOR_MODE` | `true_revenue` | The withholding basis (below). No run file sets it. |
| `TELEMETRY_DISABLED` | unset | `1`, `true`, `yes` or `on` turns telemetry off everywhere. |
| `RECONSTRUCTION_MODE` | `off` | Leave it `off`; the other values belong to a research path. |

A gitignored `.env` at the repository root is read at start and fills in any variable the shell leaves unset.
Any variable not listed here belongs to the retired model paths: leave it unset. Above all never set
`HOSTED_EXTRACTION_OPT_IN`, `OCR_ALLOW_VISUAL_PAIR`, `OCR_VISUAL_PAIR_LEGACY_VISUAL`, `OCR_REMOTE_OPT_IN` or
`VISUAL_PAIR_REMOTE_CUSTOMER_DATA_OPT_IN`, in the shell or in `.env`: each re-opens a model path, for the CLIs
as much as for the web app. Do not copy the tracked `.env.*.example` templates, and empty an old `.env` of model
settings. `run.ps1` pins those five to `0` for the web app it starts.

## Product rules

**Withholding.** Withholding divides by True revenue (`WITHHOLDING_DENOMINATOR_MODE=true_revenue`: verified plus
counted credits) by default since the owner's ruling of 2026-10-02 (the underwriter's Q7); an unset or unknown
value reads as that default. `WITHHOLDING_DENOMINATOR_MODE=legacy_eligible_deposits` selects legacy eligible
deposits (deposits less lender funding) and `WITHHOLDING_DENOMINATOR_MODE=verified_revenue` the narrower
verified basis. In either revenue mode `eligible_deposits` carries the selected denominator, and the legacy
figure stays in `legacy_eligible_deposits` on every statement; an analysis stored without a mode keeps the
legacy basis it was made under. Where the selected basis is not established, no rate is published and the
statement and its package go to review (a decision that read Approved reads Review required). The withholding
numerator is the confirmed lender debits paid plus the funder payments returned unpaid (the owner's ruling of
2026-10-02, the underwriter's Q5). As computed, worded lump-sum payoffs are taken out of the paid debits, and a
returned payment its funder re-debited is not added (`analysis/metrics.py`).

**Zelle.** Zelle deposits follow the Settings choice "Mark Zelle Payments as True Revenue" (the owner's
amendment of 2026-10-06 to the underwriter's Q3): Yes, the default, counts them in True revenue; No makes them
non-revenue (`zelle_excluded`). Both readings are stored, so the choice applies to every saved analysis at
once; the CLIs take `--zelle-true-revenue {yes,no}`.

**Lenders.** Each lender's regular payment is read for a decrease, an increase, a schedule change, a pause, a
catch-up, a new concurrent stream or a stop (the owner's request of 2026-10-06, R2-OW18;
`analysis/lender_payment_changes.py`), information only: no lender, withholding or revenue figure moves. The
owner's request of 2026-10-10 adds an "Active Positions" column to the Monthly Statements table, right before
Withholding Rate: each statement's confirmed lenders' active positions in its printed period ("2", or
"2 (+1 possible)" with a potential lender's), from the lender payment streams (`analysis/active_positions.py`).
Lender aliases are curated in `docs/lender-registry-ledger.json`; `python -m tools.build_lender_registry --write`
renders them into `analysis/classification_registry.py` and regenerates `docs/lender-registry-evidence.md`
(`--check` validates).

**Dashboard.** Since the owner's request of 2026-10-11 the dashboard and the CSV and Excel downloads show True
revenue with Held for review and Non-revenue beside it; Verified revenue and "Counted, not verified" stay in
the classifier, the served payload, the JSON download and the CLIs. Settings defaults: NSF carry-over off,
Zelle as True revenue Yes, all 12 flag groups shown. A statement downloads as md, html, json, csv or xlsx, a
package as json, csv or xlsx. The served analysis and the JSON, CSV and Excel downloads mask account numbers to
the last four digits, and spreadsheet cells that would start a formula are escaped. The md and html downloads
and the source view are the statement's own text, unmasked.

Where each rule is defined:

- Classification contract (categories, revenue tiers, reason codes, withholding):
  [`docs/transaction-classification.md`](docs/transaction-classification.md)
- True revenue: [`docs/superpowers/specs/2026-09-28-true-revenue-design.md`](docs/superpowers/specs/2026-09-28-true-revenue-design.md) (tiers in §5.1 to §5.3)
- Lender scope and flag groups: [`docs/superpowers/specs/2026-09-24-lender-detection-design.md`](docs/superpowers/specs/2026-09-24-lender-detection-design.md) (§2)
- ADB doctrine (calendar days of the printed period, one published figure): the docstring of [`analysis/adb.py`](analysis/adb.py)
- NSF (R18 and R18 amended) and no hosted extraction on parser failure (Ruling A):
  [`docs/moneythumb-replacement/PHASE2_RULINGS.md`](docs/moneythumb-replacement/PHASE2_RULINGS.md)
- Currency (native currency, no FX): [`docs/moneythumb-replacement/CURRENCY_DOCTRINE.md`](docs/moneythumb-replacement/CURRENCY_DOCTRINE.md)

## Privacy and licensing

- Statements are customer data. No statement value, name, account number or copied page text goes into code,
  tests, fixtures, docs or commit messages; tests use fabricated rows. Guards:
  `tests/test_no_statement_hardcodes.py` and `tools/privacy_scan_branch.py` (scans a branch's added lines for
  the documents' printed tokens). Only the 109 pinned corpus PDFs are tracked; the rest of `Bank Statements/`
  is ignored. The data directory is enforced outside the checkout.
- Masking happens only at the web app boundary: `analyze.py` and `batch.py` output keeps account numbers as
  printed, so treat it as customer data.
- Telemetry (on by default) carries hashes, registry ids, codes, counts and timings only, never account
  numbers, amounts, transaction text, dates, the bank label or filenames
  ([`docs/moneythumb-replacement/H3_SCHEMA.md`](docs/moneythumb-replacement/H3_SCHEMA.md)). It is append-only.
- Discovery and benchmark reports mask account numbers to the last four digits; discovery reports name relative
  paths and folder labels, so they stay local (gitignored).
- The server makes no outbound calls. The dashboard page loads its web fonts from Google Fonts in the browser;
  that request carries no statement data.
- Licensing: native text uses PyMuPDF (AGPL-3.0 or a paid licence) and page counts and previews use poppler
  (GPL). The owner's licensing rule excludes both for a licensed product; moving to pypdfium2 is step L0 of the
  commercial roadmap draft, which is not approved
  ([`docs/superpowers/specs/2026-09-27-commercial-roadmap-design.md`](docs/superpowers/specs/2026-09-27-commercial-roadmap-design.md)).

## Project status and docs map

The deterministic reader is the product: 84 parsers, classification version 5.9, the corpus gate at 105 pass,
3 withheld, 1 refusal. A generic **text-first reader** for digital statements no parser recognises is planned,
not built: [`docs/superpowers/specs/2026-09-24-text-first-reader-design.md`](docs/superpowers/specs/2026-09-24-text-first-reader-design.md)
(its references to the visual pair predate the 2026-10-13 ruling that no model is used).

**Read first:** the rule documents under [Product rules](#product-rules), in that order, then the docstring of
`corpus_gate.py` and [`docs/agent-handoffs/TRUE-REVENUE-HANDOFF.md`](docs/agent-handoffs/TRUE-REVENUE-HANDOFF.md),
the latest handoff. Load-bearing data: the two audit CSVs, `docs/lender-registry-ledger.json` and
`docs/lender-registry-evidence.md`.
Historical, read for background only: the rest of `docs/moneythumb-replacement/` (its architecture and master
plan describe the retired model fallback), the cell briefs in `docs/agent-handoffs/`, and the July specs and
plans under `docs/superpowers/`. The September plans there are finished implementation records.
