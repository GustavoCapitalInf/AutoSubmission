# Wave 0 Execution Brief

Author: Ocean. Date: 2026-08-06. Status: approved scope — H-1, H-6, D-2 only.
Constraint: minimum agent count; no scope beyond these three tasks.

---

## 0. Agent allocation (recommendation)

**Two implementation agents.** File ownership is cleanly disjoint, so two is safe and
one would serialize unrelated work:

- **Agent A (HARBOR scope):** H-6 then H-1, sequentially — they share `conftest.py`
  and H-6's path fix is a prerequisite hygiene step for H-1's corpus tooling.
- **Agent B (DELTA scope):** D-2a only (see §4 split ruling) — `webapp/` + `run.ps1`,
  zero file overlap with Agent A.

Do not use a third agent. If usage pressure demands a single agent, run H-6 → D-2a →
H-1 in that order (H-1 is the largest and benefits from landing last against a stable
tree); but two agents is the recommended configuration.

## 1. D-2 split ruling

**Yes — split.** Wave 0 executes **D-2a (development-server safety)** only:

- **D-2a (Wave 0, now):** disable debug mode; serve via a production WSGI server
  (waitress — Windows-friendly, ~5-line change); explicit localhost binding by
  default; server-side upload validation (size cap, PDF magic-byte check, file-count
  and page-count caps); `Content-Disposition` filename sanitization; CSV/XLSX formula-
  injection guard; account-number masking in webapp-served exports (JSON/CSV/XLSX).
- **D-2b (deferred to Wave 1, with D-1):** API-key auth, rate limiting, deployment
  procedure/runbook. Rationale: auth and rate limiting interact with the persistence
  and job-store decisions (D-1) and would be partially throwaway if built against the
  in-memory store; none of them are RCE-class risks once debug mode is off. The
  RCE-class and data-leak-class items (R-19, R-23, R-24, R-25) are all in D-2a.

Two Ocean pre-decisions for D-2a so the agent doesn't improvise policy:
1. **Masking format:** last 4 digits, `****1234`. Applies to every webapp-served
   surface (`/analysis`, `/download/*`, `/package_analysis`, `/package_download/*`).
   The CLI (`batch.py`, `analyze.py --json`) is a local operator tool and is OUT of
   Wave 0 scope — do not touch it.
2. **Implementation locus:** masking happens at the **webapp boundary** (a response-
   shaping helper in `webapp/`), NOT in `analysis/serialization.py`, which is
   protected (fail-closed contract, additive-only, Ocean-gated).

## 2. Task cards

### H-6 — Documentation & fixture corrections (RISK R-31; MASTER_PLAN P0 hygiene)

- **Scope (exact):**
  1. `conftest.py`: fix `samples_dir` from `PROJECT_ROOT / "BankStatements"` to the
     real `Bank Statements` folder; add a cheap existence assertion so a future rename
     fails loudly.
  2. `PROJECT_GOAL.md` "Current Baseline": update stale counts (323→523 tests,
     105→109 PDFs, 103/102→106 PASS / 3 WITHHELD) with an as-of date.
  3. `docs/backlog.md`: correct `BankStatements/...` path references.
- **May modify:** `conftest.py`, `PROJECT_GOAL.md`, `docs/backlog.md`. Nothing else.
- **Acceptance:** full suite green (523); no fixture consumer breaks; counts match
  `pytest --collect-only -q` and the audit CSVs.
- **Required tests:** existing suite only, plus the samples-dir existence assert.
- **Regression risk: minimal.** Docs + a fixture path only the deselected live test
  consumes today.

### H-1 — CI corpus gate (RISK R-7; MASTER_PLAN P0-1)

- **Scope (exact):** make the corpus-wide guarantee automatic. Wire
  `adb_forensic_audit.py` and `balance_forensic_audit.py` into an opt-in but
  enforced gate: a `corpus` pytest marker (or a single runner script) that
  (a) verifies all 109 corpus PDFs are present with pinned SHA-256s,
  (b) re-runs both oracles, (c) fails red on ANY drift from
  `docs/adb-audit-results.csv` / `docs/balance-metrics-audit-results.csv`.
  Default dev run (`pytest`) stays fast — the gate runs via `pytest -m corpus` (or
  `python run_corpus_gate.py`) and is documented as REQUIRED before merge in
  README + MERGE_PLAN reference. If a hosted-CI config (e.g. GitHub Actions) is
  feasible in this repo, add it; if no remote CI exists, the enforced local gate +
  documentation is the Wave 0 deliverable.
- **Design constraint (must confirm before coding):** the gate must run **offline
  deterministic paths only** — no live OCR endpoint, no Gemini calls. The 6 scanned
  corpus PDFs must be covered via the audit scripts' existing cached-artifact
  conventions; if any statement would require a live model call, the gate skips it
  EXPLICITLY with a named, counted skip (never silently) and reports the coverage
  denominator. Document actual wall-clock runtime.
- **May modify:** `pytest.ini` (marker), `conftest.py` (marker plumbing — after H-6
  lands), new `tests/test_corpus_gate.py` and/or a small runner script, CI config
  file (new), `README.md` (run instructions), `adb_forensic_audit.py` /
  `balance_forensic_audit.py` **CLI/exit-code surface only**.
- **Must NOT modify:** the oracle logic inside the two audit scripts (independent-
  oracle property is load-bearing — `tests/test_balance_metrics_audit.py` already
  asserts they never import `analysis.adb`/`analysis.metrics`; that assertion must
  keep passing), the audit CSVs (the gate consumes them; it never regenerates them),
  anything in `analysis/`, `webapp/`, `ocr/`.
- **Acceptance:** deliberately corrupting one expected value (locally, not committed)
  turns the gate red; restoring turns it green; runtime documented; default `pytest`
  run unchanged in duration; skip list (if any) explicit and justified.
- **Required tests:** the gate itself, plus a red/green demonstration recorded in the
  PR description.
- **Regression risk: low.** Purely additive test infrastructure. Real risks are
  operational: gate runtime, and accidental dependence on live endpoints — both
  addressed by the design constraint above.

### D-2a — Webapp development-server safety (RISKS R-19, R-23, R-24, R-25)

- **Scope (exact):**
  1. `webapp/app.py:1156-1157`: `debug=False`; serve via waitress; bind 127.0.0.1 by
     default with an env override; `run.ps1:43` updated to match.
  2. Upload validation in `/upload` (`app.py:923-952`): `MAX_CONTENT_LENGTH` (100 MB —
     make the existing UI label true), per-file PDF magic-byte check, file-count cap,
     page-count cap (reject with JSON error, consistent error shape).
  3. `Content-Disposition` sanitization for `/download` (`app.py:1148-1152`) —
     whitelist-sanitize the base name.
  4. CSV/XLSX formula-injection guard (`app.py:110-115, 151-156` and the XLSX cell
     writer): prefix-escape cells beginning with `=`, `+`, `-`, `@`, tab, CR.
  5. Account-number masking (last 4) in all webapp-served payloads/exports, applied at
     the webapp boundary per §1 ruling.
- **May modify (exact allowlist — nothing else):** `webapp/app.py`;
  `webapp/jobs.py` (only if upload-validation plumbing requires it); `run.ps1`
  (launcher flags/env only); `requirements.txt` (add waitress);
  `tests/test_webapp_app.py` (pinned-expectation updates as documented intentional
  deltas); new `tests/test_webapp_security.py`; `static/app.js` /
  `templates/index.html` ONLY if masking/limits break rendering (minimal diffs).
- **Must NOT modify:** `webapp/worker.py` (hard-excluded — if genuinely needed, stop
  and ask Ocean); `README.md` (HARBOR owns it this wave — keep `python -m webapp.app`
  as the entry point and serve via waitress from the `__main__` block so documented
  launch commands stay true); `conftest.py`; `pytest.ini`; anything in `analysis/`
  (especially `serialization.py`), `ocr/`, `docs/`; `batch.py`; `analyze.py`;
  corpus/audit assets. No auth, no rate limiting, no persistence, no queue changes
  (all deferred: D-1, D-2b, D-4).
- **Acceptance:** Werkzeug debugger unreachable; oversize/non-PDF/too-many-file
  uploads rejected server-side with JSON errors; hostile filename produces a safe
  header; a description cell starting with `=` opens inert in Excel; no webapp-served
  surface contains a full account number; full suite green.
- **Required tests (new):** upload rejection matrix (size/magic/count), header
  sanitization, formula-escape round-trip per export format, masking present in
  `/analysis`, statement CSV/XLSX/JSON, package JSON/CSV/XLSX.
- **Regression risk: moderate — the highest in Wave 0.** Two known blast surfaces:
  (a) `tests/test_new_statement_corpus.py` pins exact export values — if account
  numbers appear in pinned rows, fixtures must be updated as a **documented
  intentional delta** in the PR, never loosened; (b) the dashboard reads
  `statement.account_number` and also regex-falls-back over raw markdown
  (`app.js:250-271`) — verify the UI still renders a masked value rather than
  re-deriving an unmasked one from `/markdown`. Note and flag: `/markdown` and
  `/result` still expose raw OCR text containing full account numbers; documenting
  that residual exposure (not fixing it) is in scope — the fix belongs with auth
  (D-2b), since masking OCR text would corrupt the analyst's source view.

## 3. Cross-task matrix

| | H-6 | H-1 | D-2a |
|---|---|---|---|
| **Files** | conftest.py, PROJECT_GOAL.md, docs/backlog.md | pytest.ini, conftest.py, new tests/runner, CI config, README, audit-script CLI surface | webapp/*, run.ps1, requirements.txt, webapp tests |
| **Overlap** | conftest.py with H-1 | conftest.py with H-6 | none |
| **Depends on** | — | H-6 (conftest path) | — |

- **Protected across all three (unchanged from MASTER_PLAN §4 + MERGE_PLAN):**
  `analysis/adb.py`, `analysis/reconcile.py`, `analysis/metrics.py`,
  `analysis/transaction_classifier.py`, `analysis/serialization.py`, all parser
  modules, `ocr/`, the corpus (`Bank Statements/`), `moneythumbResults/`, the audit
  CSVs, and the audit scripts' oracle logic.
- **Parallelism:** Agent A (H-6→H-1) and Agent B (D-2a) fully parallel — zero shared
  files. H-6 and H-1 must be sequential within Agent A.
- **Implementation order:** H-6 → {H-1 ∥ D-2a}.
- **Merge order:** **H-6 → H-1 → D-2a.** H-1 lands before D-2a per MERGE_PLAN rule
  ("no PR merges without the corpus gate green") and because D-2a's masking touches
  export surfaces the balance audit inspects — D-2a must then prove the gate stays
  green (or document the intentional fixture deltas) on top of the established
  baseline, rather than the baseline being captured on top of masking.
- **Standing criteria (every PR):** full suite green; corpus audit byte-identical or
  intentional deltas documented and Ocean-approved; no new statement-specific
  constants; no protected-module diffs.

## 4. Out of scope for Wave 0 (explicit)

D-2b (auth, rate limiting, deployment runbook), D-1 (persistence), D-3 (cache), all
REEF/LEDGER/SONAR tasks including R-1 (hardcode purge — P0 but not approved for this
wave), H-2 (MoneyThumb harness), and any CLI export changes.
