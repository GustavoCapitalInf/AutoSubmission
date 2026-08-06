# CI-1 / CI-1b / CI-1c — Remote corpus-gate repair: findings

Agent C (HARBOR), 2026-08-06. Branch `wave2-proof` (CI-1 merged as `1c82a2b`,
CI-1b as `91d5d92`; CI-1c follows on the same branch). Repo
`GustavoCapitalInf/bankStatementAnalysis` (private, User-owned).

**Headline: the remote gate was never broken by billing, plan, or permissions.**
It was four independent problems in a queue, each one only visible once the
previous was cleared, and each fixed in turn:

| # | Failure | Nature | Status |
|---|---|---|---|
| A | Runner never acquired (31122891522) | GitHub-side transient | cleared itself |
| B | No poppler/tesseract on the runner (31128260273) | environment | fixed, CI-1 |
| C | Tesseract 5.3.4 vs 5.5.0 OCR drift (31128649695) | reproducibility | fixed, CI-1b |
| D | `folder` column separator, Windows vs Linux (31128834443) | cross-platform metadata | fixed, CI-1c |

Each fix moved the run one step further: D is the first run whose test suite
passed on hosted infrastructure *and* whose gate step actually executed. No
financial value has drifted at any point, and **no account-level action is
required from Gustavo.**

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

## 3. The tesseract-version risk: materialized, then resolved (CI-1b)

**Predicted here, then it happened.** Run **31128649695** (the first run with the
apt step) got further than any run before it: system dependencies green,
byte-identity check green, `797 passed` — and then **4 failures, all `columbia`,
all `RuntimeError: no deterministic parser matched this statement`**:

- `test_new_statement_ledger_and_independent_daily_balances[columbia]`
- `test_new_statement_revenue_lender_and_transaction_metrics[columbia]`
- `test_new_statement_printed_average_terminology_and_integrity`
- `test_new_statement_api_and_exports_preserve_authoritative_values`

`first_farmers` passed on the runner's tesseract; the drift narrowed to one
document. The gate step still never executed, because the suite step fails
first. Note what the error is: not a wrong number but *no parser claiming the
statement at all* — the runner's OCR text diverged enough from a 5.5.0 dev box
that Columbia's detection strings no longer matched. Nothing about the product
changed between the two machines.

The version gap, from the step this task added in CI-1 (which is exactly why it
prints them):

| | Runner (ubuntu-24.04) | This dev box |
|---|---|---|
| tesseract | **5.3.4** | **5.5.0.20241111** |
| leptonica | 1.82.0 | 1.85.0 |
| poppler | 24.02.0 | 24.08.0 |

**Confirmed as drift, not a masked regression.** Before changing anything, all
four tests were re-run on this box: `4 passed in 18.68s`.

**Resolution (Ocean's ruling, CI-1b).** The two image-only fixtures are now
served from the committed OCR artifacts in `tests/corpus_cache/`, keyed by the
SHA-256 of the source PDF — exactly how `corpus_gate.py` has always resolved
scanned statements. `corpus_artifacts.cached_markdown` verifies each artifact
against its manifest pin on every read, so a tampered artifact raises instead of
quietly moving an assertion. The served markdown is byte-identical to what this
machine's tesseract produces, so **no asserted value changed** — only where the
text comes from:

| Fixture | Source PDF SHA-256 | Manifest `artifact_sha256` | Served markdown SHA-256 | Bytes |
|---|---|---|---|---|
| columbia | `0CBD2AD897B90137…` | `44BCB603BF57CDFE…3147` | `44BCB603BF57CDFE…3147` | 10,622 |
| first_farmers | `58CB0DCC7460A445…` | `C53FB08BDA7C02CB…EBA5` | `C53FB08BDA7C02CB…EBA5` | 6,183 |

Live OCR coverage is preserved, not deleted:
`test_live_tesseract_reproduces_the_committed_artifact_reports` re-OCRs both
fixtures with the local binary and asserts the resulting report equals the
artifact-served one. It carries the **`live`** marker, so `pytest.ini`'s addopts
deselect it from the default run and `pytest -m live` exercises it. `live` is
documented as "hits the real OCR endpoint"; this widens it to "runs real OCR
rather than a committed fixture". A dedicated `tesseract` marker would be
cleaner, but registering it *and* keeping it out of the default run needs a
`pytest.ini` edit, which was outside CI-1b's allowlist — a two-line change for
Ocean if preferred. The test also skips (never fails) where no tesseract binary
exists.

Proof that the runner's condition is now green: with tesseract removed from
`PATH` entirely, `tests/test_new_statement_corpus.py` is `18 passed, 2
deselected`, and `-m live` is `2 skipped`. Full suite: `803 passed, 4
deselected`.

**Nothing was deselected and no assertion was loosened.** Deselecting on CI was
explicitly rejected; the workflow comment still says so.

## 3b. The last cross-platform gap: path separators (CI-1c)

Run **31128834443** is the one that finally got there: `Default test suite`
**green on the runner** for the first time, and the `Corpus gate` step
**executed remotely** for the first time. It went RED on `adb_audit` and nothing
else, and every detail line was one shape:

```
[FAIL] adb_audit: 109 statements reproduce every audited ADB field ...
         adb: Others/Altana/Altana april 26.pdf [folder] expected 'Others\Altana', got 'Others/Altana'
         adb: Others/B1/b1 april 2026.pdf       [folder] expected 'Others\B1',     got 'Others/B1'
         ...
```

`inventory`, `foreign_files`, `source_integrity`, `balance_audit` all PASS.
**Zero financial fields drifted.** The ADB audit renders its `folder` column
with `os.sep`, so the CSV committed from Windows pins `Others\Altana` while the
Linux runner reproduces `Others/Altana` — the same folder, a different
separator. It affects the **17 rows in nested folders (9 distinct folders)**;
the other 92 sit one level down and have no separator to disagree about. The
balance audit was immune because its `path` column is already written
`.as_posix()`.

**Fix (CI-1c), in the gate's comparison layer:** `PATH_VALUED_FIELDS =
{"folder", "path"}` and a `comparable(column, value)` helper that normalises
backslashes to forward slashes for exactly those columns before comparing.
Explicitly *not* a blanket replace across all columns — that would silently
equate two genuinely different values that happen to contain a backslash (a
`root_cause` or an escaped regex), which is the opposite of what the gate is
for. `statement` is deliberately excluded too: a filename may legitimately
contain a backslash on POSIX, and that must still fail.

No CSV was re-baselined and no oracle logic was touched. One additional
one-liner in `adb_forensic_audit.py`'s row assembly (report metadata, not
oracle math) now writes `folder` with `.as_posix()`, so a future regeneration
is platform-neutral instead of flipping those 17 rows depending on who ran it.
The gate-side normalisation is what makes today's committed CSV work either
way.

### Still open, informational

Run 31128260273's log carries the annotation that `actions/checkout@v4`,
`actions/setup-python@v5` and `actions/upload-artifact@v4` target Node 20 and
are being **forced onto Node 24**. A future maintenance bump (`checkout@v5`,
`setup-python@v6`, `upload-artifact@v5`) is the eventual fix; unrelated to any
failure seen so far.

---

## 4. Operator action required from Gustavo

**None at the account level.** No billing change, no spending limit, no plan
change, no org/repo setting. All three of the account-level hypotheses in the
task card were checked and are ruled out by run 31128260273 executing.

The one thing an agent cannot do is the last step:

1. Merge `wave2-proof` (CI-1c) to `main` and push — pushing is outside every
   agent's mandate.
2. Dispatch the workflow. **Push triggers do not currently create runs** (see
   CI-2 in `WAVE2_EXECUTION_LOG.md`), so use
   `gh workflow run corpus-gate.yml --ref main`, then
   `gh run watch $(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')`.
3. **Expected: the first fully green run.** Suite green (no live OCR), and the
   gate step green — `adb_audit` included, now that path-valued columns compare
   separator-agnostically. That closes CI-1's acceptance: the remote gate stops
   depending on developer discipline.
4. **If anything is still red,** it is a new problem rather than a known one:
   A–D above are all fixed and each has a test or a printed version pinning it.
   Read the failure before touching anything.
5. **If the job is again "not acquired by Runner of type hosted":** re-run it.
   That is Failure A, it is GitHub-side, and it cleared itself once already.

## 5. Acceptance status against the CI-1 card

| Card requirement | Status |
|---|---|
| Diagnose root cause | **Done** — two causes, both identified with run-level evidence |
| Minimal workflow adjustment if implicated | **Done** — one apt step; documented header |
| Document root cause in workflow header | **Done** |
| Green run of the full workflow on `main` | **Not achievable by this agent** — requires a push/dispatch. Every known cause is fixed: runner acquisition (transient, cleared), system binaries (CI-1), OCR version drift (CI-1b). Verification is §4 step 2. |
| Do not change billing | Not touched (and not implicated) |

## 6. Change log

| Date | Task | Change |
|---|---|---|
| 2026-08-06 | CI-1 | Diagnosed both failures; added the runner system-dependency step; documented the transient in the workflow header. |
| 2026-08-06 | CI-1b | Predicted tesseract drift materialized on run 31128649695 (4 × columbia). Scanned fixtures now served from the committed artifact cache; live-OCR path preserved behind the `live` marker. §3 rewritten. |
| 2026-08-06 | CI-1c | Run 31128834443: suite green on the runner, gate step ran remotely for the first time, RED on `adb_audit` only — 17 nested-folder rows differing by `os.sep` alone. Path-valued columns now compare separator-agnostically (`PATH_VALUED_FIELDS`); audit writer emits POSIX folders. See §3b. |
