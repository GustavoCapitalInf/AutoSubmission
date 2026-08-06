# Wave 2 Execution Log — reviews, rulings, merges

Author: Ocean. Running record; newest entries appended. Merge queue:
H-0 → CI-1 → R-2 → D-3 → O-3 → R-3 → R-4 → H-3 → DSC-1.

---

## 2026-08-06 — D-3 (Agent B / DELTA, branch `wave2-cache`) — REVIEWED: APPROVED, awaiting merge slot

Scope compliance mechanically verified: exactly 8 allowlisted files
(+1,661/−34); `analysis/`, `ocr/`, `.github/`, `batch.py`, `corpus_gate.py`,
corpus, docs untouched; `tests/test_webapp_security.py` byte-identical.
Proofs: 846 passed (795 baseline + 51), corpus gate GREEN 106/3, zero-OCR/
zero-LLM re-upload proof through the real `run_job` with call-counting fakes,
restart durability, per-knob key partitioning (9 OCR + 4 analysis knobs),
secrets excluded from key material (verified in code). Three-stage
content-addressed cache (ocr/analysis/report) with independent stage keys;
schema v3 additive migration; Flask-free module API ready for the discovery
runner.

**Ocean rulings on Agent B's open questions (D-3):**

1. **Duplicate packages / `decision` downgrade:** flag-only stands. Decision
   semantics are underwriting policy owned by LEDGER — recorded as an explicit
   L-2 requirement ("duplicate members force `review_required` unless
   dismissed by an analyst decision row"). Dashboard rendering of the flag:
   deferred to the same task. D-3 delivered exactly its scope.
2. **Failure caching:** correct to leave failures uncached this wave.
   Deterministic "no parser matched" negative-caching is revisited when DSC-1
   measures its actual re-run cost; transient model errors must never cache.
3. **Stage-version discipline — ADOPTED AS STANDING MERGE CRITERION:** any PR
   that changes OCR or analysis output for unchanged settings must bump
   `OCR_STAGE_VERSION` / `ANALYSIS_STAGE_VERSION` in the same commit. Enforced
   by Ocean at merge time. Applied to this wave: R-2/R-3 are byte-identical
   (no bump); O-3 adds truncation fields to OCR results — **O-3's merge (which
   lands after D-3) gets `OCR_STAGE_VERSION` bumped at integration**; H-3 is
   write-only side-band (no bump).
4. **Eviction:** accepted as pre-tranche-2 decision. DSC-1 must report
   `cache.stats()` in every discovery report; size cap decided on tranche-0/1
   numbers.
5. **H-3 storage coordination:** telemetry table lands as schema v4 rebased on
   D-3's merged v3; H-3 should evaluate consuming the existing
   `event_type='cache_hit'` audit rows instead of duplicating them. Both
   points go into the H-3 dispatch prompt verbatim.

---

## 2026-08-06 — H-0 + CI-1 (Agent C / HARBOR, branch `wave2-proof`) — REVIEWED: APPROVED; **MERGED to main as `1c82a2b`, pushed**

First merge of the wave. Line-by-line review of the `corpus_gate.py` diff
performed by Ocean (merge-authority standard). Findings: re-scope is stricter
than spec where it matters — new mutual cross-check that both audit CSVs pin
the identical 109-path set (replacing the directory as completeness anchor);
explicit missing-pin failures in both inventory and integrity checks;
short-circuit red report when pinned files are absent (previously an oracle
crash); foreign-file accounting reports count + folder count with **names
withheld** (sensitivity discipline); ASCII-safe output with guard. Proofs:
801 tests green (795 → +6 synthetic gate tests); gate GREEN in the clean
worktree (0 foreign) AND against the main checkout's archive-sharing root
("3507 non-corpus PDFs present - ignored"). Three allowlist deviations
disclosed, all justified (gate's own test module, workflow inline-check
signature, README CI paragraph).

**CI-1 root cause (evidence-based, reverses the billing hypothesis):** the
original "not acquired by Runner of type hosted" failure was transient
GitHub-side capacity — a later identical dispatch acquired a runner in
seconds. The real, reproducible failure was missing poppler/tesseract on
`ubuntu-latest`, breaking 10 tests in the default-suite step before the gate
ever ran. Fixed with an apt system-dependency step; both root causes recorded
in the workflow header and `CI1_FINDINGS.md`. **No account-level action
required from Gustavo.**

**Ocean rulings (H-0/CI-1):**
1. **Tesseract version drift (columbia/first_farmers live-OCR fixtures):**
   merge as-is; evidence first. If the CI run reds on exactly those two with
   value drift (runner tesseract 5.3.x vs local 5.5.0), the follow-up is
   serving both fixtures from the committed artifact cache — never deselection.
2. **OneDrive sync instability:** archive PDF count moved 3,615 → 3,616 →
   3,620 across ~1 h. DSC-1 gains a **sync-stability precondition**: two full
   enumerations ≥10 min apart must agree (count + content hashes) before the
   dry run or tranche 0; Gustavo asked to confirm when the archive upload is
   complete.
3. Post-merge validation running in the main checkout (full suite + new gate
   with archive present) and the push-triggered CI run is being watched;
   results recorded here when they land.

**CI-2 (new finding, Ocean, post-merge): push triggers create no runs.** All
five push events since the first are registered by GitHub
(`repos/.../events`), the workflow is `active`, yet total runs ever = 2 (the
first push + manual dispatches). Every subsequent push — including Wave 1's
final push and the H-0 merge — silently created no run. `workflow_dispatch`
works instantly, so Actions itself is functional; evidence points at
GitHub-side event-delivery degradation today (consistent with the earlier
runner-acquisition failure). Interim protocol: **every merge to main is
followed by a manual `gh workflow run corpus-gate.yml --ref main`** until
push-triggered runs are observed again. Verification run of the fixed
workflow: 31128649695 (dispatch, commit 1c82a2b) — result recorded below when
it completes. If push triggers stay dead across days, escalate: check
Settings → Webhooks (none expected), GitHub status history, and open a
GitHub support ticket (account-level, Gustavo's action).
