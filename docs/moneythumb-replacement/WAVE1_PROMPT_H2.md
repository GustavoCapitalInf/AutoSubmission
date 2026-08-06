# Wave 1 — Agent A Implementation Prompt: H-2 MoneyThumb Comparison Harness

Issued by Ocean (Lead Architect), 2026-08-06. Wave 1 approved as written in
WAVE1_BRIEF.md. You are Agent A. Your first and ONLY authorized task is H-2.
R-1 is NOT authorized until H-2 is completed and reviewed by Ocean.

## Where you work

- Worktree: `C:\Users\GustavoPrietodePaula\OneDrive - Capital Infusion\Desktop\Capital Infusion Projects\bankStatementAnalysis\.claude\worktrees\mt-benchmark`
- Branch: `wave1-benchmark-parsers` (already checked out, based on main @ c3030b0).
- Python for all runs/tests: `C:/Python314/python.exe` (has every project dependency).
- Required reading before writing code (read-only reference copies, absolute paths):
  - `...\bankStatementAnalysis\.claude\worktrees\mt-lead\docs\moneythumb-replacement\FIELD_MAPPING.md`
  - `...\bankStatementAnalysis\.claude\worktrees\mt-lead\docs\moneythumb-replacement\WAVE1_BRIEF.md` (H-2 task card)
  - `...\bankStatementAnalysis\moneythumbResults\README.md` and the 6 result sets under `moneythumbResults\results\` (MAIN checkout path — this folder is untracked and gitignored by design; it does not exist in your worktree)

## Objective

Build a re-runnable offline harness that, for each MoneyThumb benchmark set,
normalizes and compares four sources — (1) original statement evidence, (2) our
pipeline output, (3) MoneyThumb output, (4) independently audited expectations where
available (`docs/adb-audit-results.csv`, `docs/balance-metrics-audit-results.csv`) —
and classifies every compared field into exactly one of:

`BOTH_MATCH_EXPECTED | OUR_SYSTEM_CORRECT | MONEYTHUMB_CORRECT | BOTH_INCORRECT |
DIFFERENT_DEFINITION | SOURCE_CONTRADICTION | INSUFFICIENT_EVIDENCE | UNRESOLVED`

MoneyThumb is NEVER automatic ground truth. Classification precedence:
1. An audited expectation exists for the field → compare both outputs against it
   (yields one of the first four outcomes).
2. No audited expectation, but the source document provides direct evidence (printed
   summary values, printed balances) → same four outcomes, citing the evidence.
3. Semantic mismatch with documented differing definitions → DIFFERENT_DEFINITION
   (record both values and both definitions; never force a winner).
4. The source document contradicts itself on this field (e.g. BMO) →
   SOURCE_CONTRADICTION (our fail-closed withholding is recorded as the defensible
   behavior, MoneyThumb's reported value as commentary — not as "correct").
5. Otherwise → INSUFFICIENT_EVIDENCE, or UNRESOLVED (queued for Ocean ruling).
A difference must never land in a "correct" bucket without evidence. You make NO
changes to production code in response to any discrepancy — findings only.

Pre-ruled by Ocean (cite these, do not re-litigate):
- MT `revenue_statistics` row "Total Revenue" actually equals net cash flow →
  DIFFERENT_DEFINITION with an MT-mislabel note.
- MT bmo_jan headline `ending_balance` reports the printed 985,600.00 despite MT's
  own `reconciled=false` / calculated 520,426.00 → SOURCE_CONTRADICTION field, with
  commentary that MT surfaced an unverified headline while we withhold.
- `klr_may` contains no analysis data (HTTP 202 stub, webhook required) → recorded
  as a capability finding (MoneyThumb produced nothing for this scanned document;
  our pipeline result is reported alongside), not a field comparison.

## Source mapping (verified by Ocean — encode as a manifest with PDF SHA-256s)

| Benchmark set | Corpus source (relative to `Bank Statements/`) |
|---|---|
| bmo_jan | `Misc/BMO_Statement_January_2026 Final-1-2 (1).pdf` |
| chase_dec | `Chase/Chase Salomon Dec 2025.pdf` |
| chase_jan_feb_mar | `Chase/Chase Salomon January.pdf`, `Chase/Chase Salomomon February 27 2026.pdf`, `Chase/Chase Salomon March 2026.pdf` (compare as a package) |
| field_trucking_nov | `Misc/Field Trucking November 2025 .pdf` (note trailing space) |
| klr_may | `Misc/KLR.May 31,2026 (1).pdf` |
| wmb_may | `Misc/WMB May 25.pdf` |

Verify the February filename by listing the folder; encode whatever is on disk plus
its hash. If any mapping fails hash/existence checks, STOP and ask Ocean.

## Our-side pipeline runs — strictly offline

- No OCR endpoint, no Gemini, no network. Resolve source text exactly the way the
  corpus gate does: reuse `balance_forensic_audit.source_markdown(path,
  ocr_cache=tests/corpus_cache)` (or `corpus_artifacts.cached_markdown`) — you may
  IMPORT `adb_forensic_audit`, `balance_forensic_audit`, `corpus_artifacts`,
  `corpus_gate`, and `analysis.*` freely, but you may not MODIFY them.
- Analyze with `analysis.pipeline.analyze_markdown(markdown, parse_mode="deterministic")`
  and serialize with `analysis.serialization.report_to_dict`.
- Package comparison for chase_jan_feb_mar: aggregate via the same code path the
  webapp uses (`webapp.app._package_analysis` imported read-only, with jobs built
  in-memory the way `balance_forensic_audit` builds them) so package semantics match
  production.

## Comparison coverage (no silent omissions)

Statement level: period start/end, beginning/ending balance, total credits/debits and
counts, ADB (ours only when validated — a withheld ADB compares as "withheld by
design", not as a missing value), NSF count, negative days, min balance. Revenue: our
verified/unverified/non-revenue trio vs MT true/nontrue credits — map as
DIFFERENT_DEFINITION-aware comparison (record both taxonomies side by side; compare
gross credits directly). MCA/lender: lender names (canonicalized), payment counts,
payment totals, funding deposits. Package level: per-month rows, cross-month balance
chaining, package totals. Capability findings: MT's missing full debit ledger, the
klr_may no-result, and any field MT emits that we deliberately IGNORE per
FIELD_MAPPING (list them as `skipped_by_verdict`, with the verdict). EVERY MoneyThumb
field must appear in the rollup as compared, skipped_by_verdict, or
capability-finding — the report must prove nothing was silently dropped.

## Output

- Machine-readable per-set report + cross-set rollup (JSON; CSV summary), plus a
  human-readable markdown summary. Reports are written to `benchmark_reports/`
  (gitignored — you add the gitignore line). NEVER committed.
- Every non-BOTH_MATCH_EXPECTED row carries: field, our value, MT value, expected
  value (if any), classification, evidence pointer (file/CSV row/statement locator),
  and free-text rationale. UNRESOLVED rows are collected into an explicit
  "for Ocean ruling" section of the summary.
- Any account number appearing in ANY report is masked to last-4 (`****1234`).
  Do not emit full transaction ledgers or account-holder addresses into reports;
  reference transactions by date+amount+truncated description (≤40 chars).

## Sensitive-content rules (hard)

- `moneythumbResults/` is READ-ONLY. Never write, move, rename, or commit anything
  under it. Never copy its files into the worktree.
- No benchmark statement content (full ledgers, holder identities, full account
  numbers) may be committed anywhere. Committed artifacts are: harness code, the
  mapping manifest (paths + hashes only), synthetic-fixture tests, gitignore line,
  README section.

## File allowlist (exhaustive — nothing else)

1. `benchmark/` — new package (all harness code lives here)
2. `tests/test_benchmark_harness.py` — new; synthetic fixtures ONLY (hand-written
   fake MT payloads / fake reports; no real benchmark or corpus content)
3. `.gitignore` — one line: `benchmark_reports/`
4. `README.md` — a short "MoneyThumb comparison harness" run-instructions section

## Protected (do not touch; stop and ask Ocean if you believe you must)

Everything else. Explicitly: all of `analysis/`, `ocr/`, `webapp/`,
`Bank Statements/`, `docs/` (including both audit CSVs), `corpus_gate.py`,
`corpus_artifacts.py`, `adb_forensic_audit.py`, `balance_forensic_audit.py`,
`tests/corpus_cache/`, `tests/` (except your one new file), `conftest.py`,
`pytest.ini`, `pyproject/requirements files`, `.github/`, `moneythumbResults/`.
If ANY non-allowlisted file seems necessary, STOP WORK on that thread and put the
question in your final report instead of touching the file.

## Acceptance criteria

1. One command (documented in README) produces classified reports for all 6 sets
   (5 field-compared + klr_may capability finding) fully offline.
2. Every compared field traceable to a FIELD_MAPPING verdict; rollup proves complete
   MT-field coverage (compared / skipped_by_verdict / capability).
3. Zero modifications under `moneythumbResults/` (harness treats it read-only and
   takes its path via CLI/env, default `moneythumbResults` relative to repo root —
   in your worktree runs you will pass the main-checkout absolute path).
4. All 8 classification outcomes are reachable and unit-tested.
5. Reports contain no unmasked account numbers (tested).
6. Full default suite green; corpus gate untouched — run `C:/Python314/python.exe
   corpus_gate.py` ONCE before handoff and attach the tail (expected GREEN,
   ~5 minutes).

## Required tests (in your one test file)

Classifier precedence tests (all 8 outcomes, including the pre-ruled cases);
normalizer tests on synthetic MT payloads (string-typed numbers, ".00" zeros,
"true"/"false" strings, percent strings); masking test on report emission; manifest
smoke test (paths exist + hashes match — skip gracefully with a named skip if run
where the corpus is absent).

## Commit requirements

- Commit ONLY on `wave1-benchmark-parsers`. Small logical commits, messages prefixed
  `H-2:`. End each message with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- DO NOT merge into main. DO NOT push. DO NOT touch any other branch or worktree.
  Ocean performs all merges.

## Handoff requirements (your final report to Ocean)

1. Commit list (hash + subject) and complete file list.
2. How to run: exact commands for harness + tests.
3. Test output tails: focused test run, full `pytest -q`, and the corpus-gate tail.
4. The cross-set rollup summary: counts per classification outcome per set, the full
   UNRESOLVED list with your analysis for each, and the capability findings.
5. Notable OUR_SYSTEM_CORRECT / MONEYTHUMB_CORRECT / BOTH_INCORRECT findings with
   evidence — especially anything touching KLR and Field Trucking (these feed R-1).
6. Any deviation from this prompt, any file you wanted but was not allowlisted, and
   any open questions. Do not start R-1 or any other task.
