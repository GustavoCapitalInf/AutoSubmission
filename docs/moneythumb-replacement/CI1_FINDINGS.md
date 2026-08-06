# CI-1 — Remote corpus-gate repair: findings

Agent C (HARBOR), 2026-08-06. Branch `wave2-proof`. Repo
`GustavoCapitalInf/bankStatementAnalysis` (private, User-owned).

**Headline: the remote gate was never broken by billing, plan, or permissions,
and the workflow content was only half the problem.** There were two unrelated
failures stacked on top of each other. One is a GitHub-side transient that
already cleared itself; the other is a real, reproducible environment gap that
this branch fixes. **No account-level action is required from Gustavo.**

---

## 1. What the evidence actually shows

### Failure A — run 31122891522 (push, 2026-08-06 17:21Z): transient, self-cleared

| Fact | Value | Source |
|---|---|---|
| Conclusion | `failure`, job `cancelled` after 15m03s | `gh api .../runs/31122891522` |
| Message | "The job was not acquired by Runner of type hosted even after multiple attempts" | run annotation |
| Steps reached | none | `gh run view` |
| `runner_name` | `""` (empty — no runner was ever assigned) | `.../runs/31122891522/jobs` |
| Labels requested | `["ubuntu-latest"]` | same |
| Billable | `UBUNTU.total_ms = 0` | `.../runs/31122891522/timing` |

### Failure A is dead — proven by run 31128260273 (workflow_dispatch, 21:22Z)

Same workflow, same `main`, same `ubuntu-latest` label, ~3h55m later:
**a runner was acquired within seconds and every step executed** (`Set up job`,
`checkout`, `setup-python`, `Install dependencies`, `Verify the corpus checked
out byte-identically` — all green). Total run 1m15s.

That single fact rules out every standing hypothesis for Failure A:

- **Not exhausted Actions minutes / spending limit $0** — a run executed 10
  minutes before this document was written. A blocked account cannot start a
  hosted job at all.
- **Not Actions permissions** — `gh api .../actions/permissions` returns
  `{"enabled": true, "allowed_actions": "all", "sha_pinning_required": false}`.
- **Not runner-label availability** — `ubuntu-latest` resolved fine on the
  second attempt.
- **Not workflow content** — the job never reached a step, and the identical
  file later ran all steps unchanged.

**Root cause of Failure A: transient hosted-runner capacity/incident on
GitHub's side.** Nothing in this repository caused it and nothing in this
repository fixes it. Operator response if it recurs: re-run the job
(`gh run rerun <id>`) and check <https://www.githubstatus.com>. Documented in
the workflow header so the next person does not re-diagnose it.

Billing note: the timing endpoint reports `billable.UBUNTU.total_ms = 0` for
**both** runs, which is not a usable signal either way. The authenticated token
carries scopes `gist, read:org, repo` — no `user` scope — so
`/users/{u}/settings/billing/actions` still returns 404 and minute consumption
remains unreadable from here. It is also no longer worth reading: execution is
demonstrably not blocked.

### Failure B — run 31128260273: missing system binaries (real, reproducible, fixed here)

The dispatched run got past runner acquisition and died in **`Default test
suite`**: `10 failed, 785 passed, 2 deselected in 33.88s`. All ten failures are
one cause — `ubuntu-latest` ships neither poppler nor tesseract, and the default
suite (unlike the gate) exercises the real local OCR ladder:

| Failures | Test | Immediate error | Missing binary |
|---|---|---|---|
| 4 | `test_new_source_inventory_is_exact[columbia, first_farmers, navigant, relay]` | `pdf2image.exceptions.PDFInfoNotInstalledError: Unable to get page count. Is poppler installed and in PATH?` | `poppler-utils` (`ocr.rasterize.pdf_page_count` → `pdfinfo`) |
| 6 | `test_new_statement_ledger_and_independent_daily_balances[columbia, first_farmers]`, `..._revenue_lender_and_transaction_metrics[columbia, first_farmers]`, `..._printed_average_terminology_and_integrity`, `..._api_and_exports_preserve_authoritative_values` | `assert None is not None` — `parse_local_tesseract(...)` returned `None` | `tesseract-ocr` |

Note the shape of this: the **corpus gate step never ran** (the suite fails
first), and the gate would not have needed either binary — it is offline by
construction and serves scanned statements from committed OCR artifacts. The
break is entirely in the suite step sharing the job.

---

## 2. What I changed

`.github/workflows/corpus-gate.yml` only (CI-1's allowlist), plus the README CI
paragraph and this document.

1. **New step `Install OCR system dependencies`**, before `Install
   dependencies`:
   `sudo apt-get install -y --no-install-recommends poppler-utils tesseract-ocr
   tesseract-ocr-eng`, then `pdfinfo -v` and `tesseract --version` so the
   runner's versions are printed in the log for comparison against a dev box.
2. **Header comment** recording both failures, why Failure A needs no fix, and
   why the binaries are installed for a job whose gate is deliberately offline.
3. **`Verify the corpus checked out byte-identically`** inline Python updated
   for H-0's new `check_source_integrity(result, corpus, balance_csv)`
   signature (H-0 changed it; leaving it would have broken this step).

Deliberately **not** changed, to avoid speculative churn: runner labels,
`timeout-minutes` (30 is not implicated — GitHub's own 15-minute acquisition
window expired first), `concurrency` (there is no queue contention: two runs
exist in the repository's entire history), action major versions.

---

## 3. Known residual risk — read before merging

Run 31128260273's log carries the annotation that `actions/checkout@v4`,
`actions/setup-python@v5` and `actions/upload-artifact@v4` target Node 20 and
are being **forced onto Node 24**. Informational today; a future maintenance
bump (`checkout@v5`, `setup-python@v6`, `upload-artifact@v5`) is the eventual
fix. Not done here — unverifiable without a push, and unrelated to the failure.

**The tesseract-version risk is the one that matters.** Two fixtures
(`columbia`, `first_farmers`) are re-OCR'd *live* by the suite and then asserted
against exact financial values. This dev box runs tesseract **5.5.0** /
leptonica 1.85.0; Ubuntu's repository tesseract is an older 5.3.x. If the runner
produces even slightly different text, those two fixtures can still be red after
this fix — the same class of instability that made the corpus gate use committed
artifacts in the first place.

**Recommended durable fix (needs Ocean's approval — it is test code, outside
CI-1's allowlist):** serve those two fixtures from the existing committed
artifact cache instead of live OCR. Both are already pinned there —
`tests/corpus_cache/manifest.json` covers `Misc/Columbia May 26 complete.pdf`
and `Misc/First Farmers 2026 01-document.pdf`, keyed by source SHA-256. That
would make the suite as version-proof as the gate. **Deselecting the tests on CI
is not an acceptable alternative** and the workflow comment says so.

---

## 4. Operator action required from Gustavo

**None at the account level.** No billing change, no spending limit, no plan
change, no org/repo setting. All three of the account-level hypotheses in the
task card were checked and are ruled out by run 31128260273 executing.

The one thing an agent cannot do is the last step:

1. Merge `wave2-proof` (H-0 + CI-1) to `main` and push — pushing is outside
   every agent's mandate.
2. The push triggers `Corpus gate` on `main`. Watch it:
   `gh run watch $(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')`.
3. **If it is green:** CI-1's acceptance is met — remote gate live, local gate
   stops being the sole merge authority.
4. **If `Default test suite` fails again on `columbia`/`first_farmers` only:**
   that is the predicted tesseract-version drift, not a regression. Compare the
   `tesseract --version` line now printed in the log against 5.5.0 and apply
   §3's cache-backed fix.
5. **If the job is again "not acquired by Runner of type hosted":** re-run it.
   That is Failure A, it is GitHub-side, and it cleared itself once already.

## 5. Acceptance status against the CI-1 card

| Card requirement | Status |
|---|---|
| Diagnose root cause | **Done** — two causes, both identified with run-level evidence |
| Minimal workflow adjustment if implicated | **Done** — one apt step; documented header |
| Document root cause in workflow header | **Done** |
| Green run of the full workflow on `main` | **Not achievable by this agent** — requires a push. Fix is committed and ready; verification is step 1 above. |
| Do not change billing | Not touched (and not implicated) |
