# Wave 2/3 Execution Log — reviews, rulings, merges

## 2026-08-07 — W3-3c (REEF-1) PROOF-COMPLETE; REVIEWED: pipeline diff APPROVED with rulings; **GEOMETRY HYPOTHESIS: NOT VALIDATED (honest negative)**

analysis/structurer/ subsystem (1,521 lines, 6 modules): evidence-decided
column/sign/period inference (balance-chain scoring, never assertion),
grounding rebuilt from the archived prototype concepts (span uniqueness,
page-anchored values, no provenance → not publishable), refusal-not-
exception, GENERIC_STRUCTURER_ENABLED opt-in default OFF (verified in code).
**Measured: "published implies correct" — zero false validations anywhere;
pinned 109 with geometry: 6 published / 5 validated / 5 fully correct /
103 refused with named reasons; 75-doc unclaimed archive sample: 5.3%
validated (flat 4.0%). Honest read: ≈+2.6 points, NOT 3a's +4 (the
ledger-identity requirement removed incomplete-ledger false wins) and
NOT the +10–17 geometry hypothesis — geometry solved reading-order as
predicted but moved documents between refusal classes, not through the
gate. Safety floor established; refusal queue is the tractable work:
no-printed-period 24% · ungrounded 20% · ledger-incomplete 17% · rows-
outside-period 16%.** Three adversarial-test defects fixed in-build
(summary-lines-as-transactions; 264 s catastrophic regex backtracking →
0.077 s; quadratic column decision). Strategic consequence: Track A
(614 withheld) is now clearly the primary coverage lever; the structurer
is the safety-floor + long-tail instrument.

**Ocean rulings:** six-line pipeline diff APPROVED as pinned (opt-in
verified); Q1 ledger_incomplete REFUSES (stands); Q2 balance-forward+1day
inference kept ONLY with inferred-provenance marking + refuse-if-posting-
predates guard (implement if absent); Q3 geometry wiring = HARBOR
integration card post-merge (rung ships off); Q4 grounding coverage 1.0
stands. Agent implementing the diff; merge on its proof.

## 2026-08-07 — Hotfix + W3-4 (HARBOR) REVIEWED: APPROVED; merged locally, push gated on the pipefail'd main-checkout corpus proof

Hotfix exactly per ruling (manifest-spelling identity at the partition
boundary; classify untouched; non-vacuous regression proven by stash).
W3-4: adjudication workspace over 3,380 distinct documents → 38.0%
variant_completeness / 27.1% generic_structurer / 246 human-queue / 54
new_parser_candidate (Huntington) / 16 junk; **registry-name-aware label
matcher caught the TD Bank→td_us trap (65 false misfiled → 3 genuine
pairs); `misfiled` is proposed by NO rule — humans write it**; movement
tool keys on hashes, deferred outside the ladder, self-comparison = zero.
Blocking finding validated: the cached baseline (`02e90a86`) carries zero
parser ids — `--enrich` hash-join from a live run is mandatory for
class×parser views.

**Ocean rulings (W3-4 open questions):** (1) ADD `parser_defect`
disposition — crashes route there mechanically (post-W3-1 they are
explicit outcomes); W3-1's ranking owns remediation. (2) Missing enrich
becomes LOUD (error unless `--allow-unattributed`); additionally Ocean
re-captures a self-sufficient canonical baseline with `--no-cache`
post-merge (also bakes in W3-1's crash fixes — supersedes `02e90a86`).
(3) Misfiled count: the registry-label matcher (24 docs / 3 pairs) is
authoritative; the report's 21 was statement_bank-derived — reconciled in
docs at the adjudication session. (4) `NEW_PARSER_VOLUME_FLOOR = 50`
accepted as proposal, surfaced to Gustavo at the adjudication session as
the one policy knob. (5) `--fail-on-regression` is an Ocean merge-protocol
gate for improvement claims, not CI (CI has no archive). (6)
`integrity_check_exception` classing: the agent's point is accepted — a
crashed check means UNKNOWN, not clean; a high-ranked `check_unavailable`
class is ruled IN as W3-2b (small HARBOR follow-up; re-baselines the
rollup while only 3 corpus anchors exist — the cheap moment to do it).

**W3-1 push landed, but the corpus-marked proof was RED (1 failure) and my
chained command's pipe swallowed pytest's exit code, so the push went
through anyway — Ocean process slip #2; all future proof chains use
`set -o pipefail`.** The failure is NOT a W3-1 regression: latent,
main-checkout-only — the on-disk `Scotiabank/` folder (archive-created,
reused by the case-insensitive FS at corpus restore) vs the manifest's
`ScotiaBank/` makes the dry run derive a disk-spelled relative_path that
string-mismatches the pinned spelling → false pinned_corpus_duplicate
(108/109 unique). Clean worktrees pass; CI (case-sensitive, no archive)
unaffected. The NEW standing corpus-marked criterion caught it on its
first main-checkout run — working as designed. **Hotfix ruled: identity
canonicalization to manifest spelling at the partition boundary (one
place), never case-blind classify; dispatched to HARBOR as task 0.**

**Dispatches (three tracks live):** REEF-1 (mt-reef) → W3-3c build per the
gate rulings (unclaimed-branch rung, grounding-gated promotion, geometry
input, default-off, propose-first pipeline diff). REEF-2 NEW agent
(mt-variants / wave3-variant-completeness) → Track A: chase×detail_coverage
217 first, layout-family method (characterize → root-cause → capability fix
or fail-closed-by-design → synthetic fixtures → honest cell measurement).
HARBOR (mt-harbor) → hotfix + W3-4 adjudication/routing tooling with the
closed disposition vocabulary and the two-run coverage-movement comparison
keyed on content hashes.

## 2026-08-07 — **W3-3b DESIGN GATE: GUSTAVO'S RULINGS RECEIVED**

1. **BOTH IN PARALLEL:** Track A variant-completeness against the 614
   (W3-2 evidence-ranked; chase×detail_coverage 217 first; layout-family /
   capability / check level — never per-statement) ∥ Track B W3-3c
   geometry-aware generic structurer. Neither blocks the other absent an
   architectural dependency Ocean identifies.
2. **W3-3c placement:** unclaimed-branch fallback rung; NOT a band-900
   registration; proven issuer-evidence registrations retain precedence.
3. **Grounding scope:** any structurer value that can influence a validated
   financial result carries source grounding/provenance verifiable by the
   existing validation system; ungrounded candidates may exist internally
   but are never promoted to publishable outputs; adapt prototype concepts,
   never merge prototype architecture.
4. **Prototype branches: tag-then-delete EXECUTED** — tags
   archive/universal-prototype-2026-08-04 (`f14282e`) and -05 (`54a9e8d`)
   pushed and verified (trees contain universal.py / grounding.py /
   parser_registry.py); both branch refs deleted; origin = main + tags.
5. **W3-4 dispatched** (on proof-green): systemic layout-family
   adjudication/routing on the ranked queue; 614-doc measurement is the
   baseline; coverage movement reported by failure class × parser family.
6. **Success metric replaced with the evidence-based targets:** ~+4 points
   demonstrated flat-input; +10–17 geometry-path hypothesis to validate; no
   predetermined number forced. Governing acceptance unchanged: zero false
   validations · protected core intact · fail closed · 109-gate green ·
   corpus-marked selection in every merge proof · improvements measured
   against the frozen 3,506-doc baseline · no customer/date/amount fixes.

Dispatch plan (armed, executes when the W3-1 corpus proof/push lands
green): REEF-1 (existing 3a agent, full context) → W3-3c per rulings;
REEF-2 (new agent, new worktree wave3-variant-completeness) → Track A;
HARBOR (existing agent) → W3-4.

## 2026-08-07 — W3-1/W3-1b REVIEWED: APPROVED; MERGED (pending corpus-marked proof → push)

Pipeline diff verified verbatim-as-approved (+26/−2; parser_exception +
integrity_check_exception flags with class-names-only notes; ParserCrashError
subclassing RuntimeError; run_integrity_checks keeps guarding policy at the
registry seam). Ruling-2 semantics precise and correct: a raising check has
NO finding — no false contradictions, asserted. Bonus leak closed: crash
messages quoting statement fragments no longer reach durable job records.
Composition with W3-2's drift guard done the right way (flags added to
INTEGRITY_FLAGS as ADVISORY — a crash must not outrank financial checks in
the diagnosis ranking). Merge-only commit separated from the protected
change (agent self-corrected). Zero xfails remain. 1,892 tests; gate GREEN
×5 byte-identical; the 53 discovery crashes re-measured → 0.

**New standing merge criterion (from REEF's self-caught regression —
a corpus-marked parity helper broke while the default suite stayed green):
every merge proof now includes `pytest -m corpus` (the corpus-marked
selection), not just the default suite + gate.** Applied to this merge
first (push chained behind it).

**Ocean ruling (open item 1):** parser_exception stays symmetric with
parser_ambiguous (flag + telemetry review class; no assess_quality
forcing). Whether either should force `manual_review_required` in the
payload is a policy decision for the W3-4 adjudication workflow —
deferred with that dispatch.

## 2026-08-07 — W3-5 MERGED (`2fdf148`) · W3-1 reviewed, pipeline diff APPROVED · 3a spike evidence delivered

**W3-5 (SONAR): APPROVED and merged** — `--scanned-visual` as tranche 3;
recovery (13) unconditional + upgrade (~159) gated on the visual read
actually analysing; three cost-justified narrowings (never escalate
unclaimed NATIVE text; never escalate on a cache hit; crashed-claims are
W3-1's); availability probe (exit 2, model-list check, class-only errors);
cache partitions proven with zero D-3 change; failure-never-cached;
deferral taxonomy tightened to terminal outcomes. 1,838 tests post-merge.
Rulings: Q1 cost line — `baidu/Unlimited-OCR` added to FREE_MODELS ($0
VENDOR is a fact; infra cost stays operational) — **Ocean process slip
logged: the ruling commit (`fa79b90`) was pushed before running its blast
radius; one W3-5 test pinned the old unpriced behavior; fixed next commit
(`f0e41a9`), red window on origin = one commit.** Q2 circuit breaker:
deferred to backlog unless tranche 3 shows need. Q3 withheld-tesseract
escalation: revisit after tranche-3 evidence. Q4 sequencing accepted:
recovery-only first (13 docs), then escalation. Tranche 3 execution
awaits: local OCR server availability (probe currently refuses —
server down; see docs/runpod-setup.md) + Gustavo's go.

**W3-1 + crash fixes (REEF): reviewed, held for one approved change.**
Boundary design accepted (Exception-not-BaseException; ParserFailure with
class names only; parser_exception outcome distinct from unclaimed;
crashes never counted as unknown-layout clusters). Crash clusters
root-caused and fixed generically (us_bank optional interest line; shaped-
but-impossible date tokens via new iso_or_none — also closes the latent
pnc/regions crash; one R-2 frozen-oracle divergence recorded explicitly).
Re-measured over the 53 archive docs: **crashes 53 → 0** (16 validated +
20 withheld / 16 withheld / 1 unclaimed — all fail-closed). **Ocean
rulings:** the pinned pipeline.py diff APPROVED + extended to guard
`integrity_checks` invocation (`integrity_check_exception` flag); NO
ANALYSIS_STAGE_VERSION bump (reasoning recorded); deviations 2/4/5
accepted. Agent implementing now; W3-1 merges only with the diff landed
and forensic proof attached.

**W3-3a spike evidence (frozen for the 3b gate):** 184 real documents
through an experimental bank-agnostic structurer behind the REAL gate —
**zero false validations** (5/5 published values correct field-for-field);
gate sufficiency proven; binding constraint = completeness not recognition
(74%→81% into the gate moved nothing through it); flat text is the wrong
input (reading-order failures dominate refusals; word geometry = largest
lever); honest re-scope of the coverage target: +4 points today, +10–17
with geometry, remainder belongs to W3-2 (614 withheld) and W3-5 (159 OCR).
Architecture proposal: structurer → same Statement → reconciliation AND
rebuilt grounding, both required, unclaimed-branch rung, default off.
**Prototype-branch final recommendation: tag both commits
(archive/universal-prototype-2026-08-04|05), push tags, then delete the
two remote refs — P2-1 was the last consumer.** All 3b decisions await
Gustavo at the design gate.

## 2026-08-07 — WAVE 3 LAUNCHED (approved by Gustavo as proposed)

Environment verified (Fable 5 lead; CLAUDE_CODE_SUBAGENT_MODEL=opus). Three
Opus 5 agents dispatched from `main@1d2f396`; W3-3c staffing decided at the
3b gate:

| Agent | Worktree / branch | Dispatched scope | Stop point |
|---|---|---|---|
| A — REEF | mt-reef / wave3-boundary-understanding | W3-1 exception boundary → crash-cluster generic fixes (AttributeError/US Bank ×36, ValueError/BofA ×16+TD 1) → W3-3a investigation spike | Propose-first on any pipeline.py diff; hard stop after 3a (design gate) |
| B — HARBOR | mt-harbor / wave3-diagnostics | W3-2 withheld-diagnostics (read-only over analysis outputs; taxonomy doc W3_2_TAXONOMY.md; withheld-3 anchor test) | Stop after W3-2; W3-4 dispatched later |
| D — SONAR | mt-sonar / wave3-visual-ocr | W3-5 visual rung into discovery ladder (cache/flags/telemetry; availability probing; no archive processing) | Stop after W3-5 |

Bindings restated in every prompt: no statement-specific fixes; protected
core; fail closed; discovery = evidence not target; agents never merge to
main; archive read-only for diagnosis, synthetic fixtures only, no content
in reports; measurements vs frozen discovery + 109 corpus are Ocean-run.
Merge order intent: W3-1 → W3-2 → W3-5 → (3a report → 3b gate with
Gustavo). Post-W3-1 merge, Ocean runs a measured discovery re-run
(cache-cheap) to quantify crash-class conversion.

---

## 2026-08-07 — W3-2 REVIEWED: APPROVED; **MERGED as `f16f1fc`, pushed** (readiness-ordered ahead of W3-1 — telemetry-only, no file conflict; REEF rebases on merge)

50 codes → 16 ranked classes; prefix-anchored mapping (hostile-description
spoof tested); withheld-3 anchor reproduces the documented forensic
diagnoses from adb-withheld-second-pass.md; zero analysis-output change
proven byte-identical; 1,803 tests; gate GREEN 106/3. Disclosed test-only
fix accepted (pre-existing I1 flake: a timestamp substring reading as an
amount; scan now excludes four shape-pinned identifier fields). README
diagnostics paragraph added by Ocean post-merge (`983afe0`).

**Ocean rulings (W3-2 open questions):** (1) `count_mismatch` platform
check = named Wave-3 ticket (protected-module change, Ocean-gated; payload
already carries the raw material) — logged, not now. (2) Withheld-only
scope STANDS; expansion to review/failed classes requires a ruling at
W3-4. (3) Cause-over-symptom precedence CONFIRMED; revisit only if the
614-scale rollup contradicts the three corpus anchors. (4) `unmapped`
carrying literal names for enum-shaped sources CONFIRMED (our constants);
free-text sources counts-only. Also logged from the survey: dead
`summary_trusted` quality vocabulary in pipeline.py (unreachable branch) —
Wave-3 hygiene ticket.

**Measured re-run COMPLETE (run `…-02e90a86`, cached, ~cheap): the
vocabulary held at scale — `unmapped 0 | 0 | 0` over all 614 withheld.**
Failure-class × parser cross-cut (parser attribution joined by content
hash from the original tranche runs; 614/614 attributed):

| Class | Docs | Top parsers |
|---|---|---|
| detail_coverage | **390** (63.5%) | **chase 217**, td_canada_native 61, rbc 48, bofa 16, pnc 14 |
| ledger_identity | 130 (21.2%) | chase 88, bofa 23, truist 8 |
| period_integrity | 32 | wells_fargo 22, chase 5 |
| balance_continuity | 26 | rbc 18, wells_fargo 5, chase_export 3 |
| posting_date_coverage | 22 | bofa 15, chase 6 |
| summary_identity / source_contradiction / adb_not_computable | 7 / 4 / 3 | scotiabank 3·ibc 2 / bmo 4 / farmers_merchants 3 |

Reading: **chase variants losing transaction rows (217 docs) is the single
largest withheld cell (35% of all withheld)**; extraction-completeness on
chase/td_can/rbc variants is the top-value remediation block, exactly the
evidence shape W3-2 was built to produce. bmo's 4 source_contradictions and
the flagged docs go to the adjudication queue (possible genuine document
defects, not code). This table is W3-4's ranked queue and 3b design-review
input.

---


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
3. **Post-merge validation LANDED (main checkout, archive present): 801
   passed; gate GREEN, "Ignored: 3507 non-corpus PDFs", 106/3, 341.3 s.**
   H-0's purpose proven in the real environment. (Foreign count still moving
   with OneDrive sync — 3,507 per gate vs 3,511 per a later enumeration; the
   DSC-1 sync-stability precondition stands.)

---

## 2026-08-06 — O-3 (Agent D / SONAR, branch `wave2-ocr-integrity`) — REVIEWED: APPROVED, awaiting merge slot (after D-3)

Scope verified: 5 files, all under `ocr/` + new tests; protected trees
untouched; zero edits to existing test modules (the `PageText` str-subclass
carries model metadata without any signature change — clean design). Proofs:
827 passed (+32), corpus-marked full-ladder parity test (2 passed under
`-m corpus`), gate GREEN, **zero corpus pages flagged on all three probes**.
Detection: model-side (`finish_reason` length / token-ceiling — previously
discarded by the client on both response paths) + high-precision structural
tail signals (unclosed table/row/cell, partial tag), with three higher-recall
signals explicitly rejected as false-positive generators. Flag-only confirmed:
`to_markdown()` byte-identical, proven by test.

**Ocean rulings (O-3):**
1. **`ocr/document.py` allowlist question: APPROVED** — it is inside the
   brief's `ocr/` ownership and the surfacing instruction required it;
   the dispatch prompt's parenthetical was illustrative, not exhaustive.
2. **Flag surfacing to operators:** adopted as an H-3 telemetry field
   (per-statement truncated-page count/indices) — goes into the H-3 dispatch
   prompt. Webapp payload surfacing deferred to the same integration.
3. **Automatic re-OCR routing:** deferred until DSC-2 tranche 2 provides a
   real base rate. `_MAX_TOKENS = 4096` literal: candidate for H-4 threshold
   calibration; no change without tranche-2 evidence.
4. **O-3 merge-integration checklist (Ocean executes at merge):** bump
   `OCR_STAGE_VERSION` (cached OCR payload shape gains `page_integrity`);
   verify D-3's cache round-trips `page_integrity` on hit (D-3 predates O-3 —
   if the cached payload drops the field, a follow-up test + fix lands with
   the merge); corpus-finding note: the validated corpus contains no
   visual-OCR text, so model-side signals are exercised only by fixtures
   until tranche 2.

**CI verification run 31128649695 (fixed workflow, commit 1c82a2b):**
system-dependency step GREEN, byte-identity GREEN; suite step failed with
exactly the predicted residual — narrowed to **columbia only** (4 failures,
"no deterministic parser matched"; first_farmers passed): runner tesseract
5.3.x output vs local 5.5.0. Per the pre-merge ruling, Agent C resumed with
**CI-1b**: serve the live-tesseract fixtures from committed artifacts (never
deselect, no assertion changes), keep a real-tesseract opt-in marker, prove
version-drift by local rerun first. 10 → 4 failures progress; gate step still
pending its first remote execution.

---

## 2026-08-06 — R-2 (Agent A / REEF) — REVIEWED: APPROVED; **MERGED as `74acb99`** · D-3 **MERGED as `c7cfb7e`** · O-3 **MERGED as `38c8cd0`**

R-2: 28 money clones → `analysis/money.py` with differential-equivalence
proofs (every pre-R-2 body frozen as an oracle, asserted identical over a
~200-input matrix); 18 date bodies → `date_tokens.py`; 23 table bodies →
`tables.py`; inversion removed for all 13 parsers (one protected-line remnant
in pipeline.py, deleted by R-3 §7.2, guard-allowlisted). 908 tests; gate
GREEN ×4; zero protected files (verified mechanically). Deviations 1–4 all
accepted with their stated rationales. Combined tree after the three merges,
full validation in the archive-sharing main checkout: **999 passed, 5
deselected; gate GREEN (106/3, 3,507 foreign ignored, 363.7 s)**. Local main
= `38c8cd0`; origin/main = `74acb99` — push + CI dispatch batched with the
D-3b + CI-1c merges.

**D-3b MERGED (`33c7bf0`, ff): APPROVED** — page_integrity round-trips the
cache; OCR_STAGE_VERSION 1→2 (first exercise of the standing rule); 1003
tests; getattr-tolerance for pre-O-3 document shapes accepted (matches
ocr/truncation's documented reader contract). H-3 note: truncation facts read
off the document object (safe on hit and miss); freshness from `cache_hit`
audit rows.

**CI-1c MERGED (`bac6149`): APPROVED** — quantified root cause (17/109 rows,
9 nested folders; `folder` the only backslash column anywhere); named
PATH_VALUED_FIELDS normalization on both compare sides with three
masking-prevention tests; offline Linux simulation reproduces run 31128834443
in both directions; ADB writer emits POSIX for future regenerations (report
surface only). 1004 tests; local gate GREEN. **Batch `D-3`+`O-3`+`D-3b`+
`CI-1c` pushed (origin/main = `bac6149`); verification run 31129048067
dispatched — expected to be the first fully green remote run.** CI failure
genealogy now documented in CI1_FINDINGS.md: four independent, serially
masked causes (runner transient → missing binaries → OCR version drift →
path separators), zero financial drift at any point.

---

## 2026-08-06 — R-3.0–R-3.3 landed on branch; **STOP-THE-LINE FINDING at R-3.4; Ocean rulings issued**

Agent A executed R-3.0 (baseline recorder + parser_expectations.json, 1008
tests), R-3.1 (registry machinery, +27), R-3.2 (per-parser detect, 1035),
R-3.3 (sub-dispatch promotion — chase_export/rbc_fr/td_can_native as
registrations, 1182 tests), every stage suite- and gate-green, pipeline.py
untouched. Measured parity: unclaimed 0, wrong-parser 0, outscored 0,
**ambiguous 45** — which is the finding:

**Five parsers detect by bare bank-name substrings that also match
counterparty mentions in other banks' statements** (capital_one claims 38
foreign corpus docs; bmo 7 — including Zelle reference ids containing "BMO";
regions 3; scotiabank 3; bank_of_america 1). capital_one was correct only by
chain position (41st of 43). Full evidence: R3_DETECTION_FINDING.md. Agent
correctly did not fix (detection-semantics change beyond approved mechanical
transcription); correctly rejected ~52 supersedes edges (chain order
re-encoded), score-lowering (forbidden), and a positional-offset rule
(corpus-fitted constant of the R-1-purged kind).

**Ocean rulings:** (1) issuer-furniture required markers APPROVED for the
five parsers — admissible classes: issuer domains/headings/footers/service
furniture; prohibited: customer data, offsets, corpus-fitted constants;
per-marker detection-positive + cited detection-negative fixtures; target
ambiguous 45→0, parity 109/109, gate byte-identical. Off-corpus semantic
shift is INTENTIONAL: these parsers now under-claim (fail-safe) instead of
over-claim. (2) Agent selects capital_one/scotiabank markers itself; Ocean
reviews the completed five-parser table at the R-3.4 stop. (3) Wave-3
backlog ticket: "BMO" 3-char substring + "BUSINESS ACCOUNT 01180" residual
fragment (R-1 residual sweep); fix now only if inside the five parsers'
guards. New mandatory stop after R-3.4 regardless of supersedes outcomes.
Also noted: demo_national claims zero corpus documents (→ R-4 list);
detect-sweep cost measured at 2.95 ms mean/doc ≈ 10 s for the full archive.

**Docs-merge note:** the execution log now merges to main (`2dc45d3`) so
agents can read rulings in-tree; docs-only merges are exempt from the
dispatch-after-merge protocol (they cannot affect the gate), recorded here
as an explicit Ocean ruling.

**Run 31129048067: `completed success` — FIRST FULLY GREEN REMOTE CORPUS-GATE
RUN (6m43s, suite + gate + report artifact). CI-1 CLOSED; MASTER_PLAN P0-1 /
gap G4 now enforced remotely as well as locally.** Remaining CI item: CI-2
(dead push triggers) — manual-dispatch-after-merge protocol stays in force;
Gustavo's billing-page check is the outstanding diagnostic.

---

## 2026-08-06 — R-3.4 REVIEWED: APPROVED; **R-3.0–3.4 MERGED to main as `55626eb` (ff), pushed; run 31131672673 dispatched**

Marker table verified as approved-class issuer furniture (headings, footer,
domain, legal name); scotiabank's `01180` account fragment removed with
regression guard; near-miss band (0, 0.5) tested per marker — a deliberate
DSC-2 "almost matched" telemetry hook. Parity after markers: **ambiguous 0,
unclaimed 0, wrong-parser 0, fallthrough 0** (RFC §4.3 closed by
measurement). 1,224 tests; gate GREEN per stage; pipeline.py −160/+45 with
zero bank knowledge (verified: the single grep hit is the pre-existing
regions REPAIR import, narrowed — R-8 leftover as ruled). Judgment calls
accepted: inert nested sub-dispatch calls kept (flagged), Chase-export note
strings moved into registration data. Detect sweep re-measured: 3.04 ms/doc
≈ 10.7 s for the full archive. New defect-class observation logged: the
`<!-- SOURCE: filename -->` echo puts filename text into detection evidence
— a SOURCE-invariance conformance check for all 46 registrations is added to
R-4 scope (findings, not fixes).

**Run 31131672673 (R-3 merge, `55626eb`): `completed success`** — second
consecutive fully green remote run; the registry dispatch is remotely
verified.

---

## 2026-08-06 — R-4 conformance harness DONE on branch; three defects found; **R-4b fix-phase dispatched**

R-4 (commit `7f77661`, tests+docs only, pipeline.py untouched): 46/46
detection-positive; 46×45 = 2,070 cross-product with 0 cross-claims; 46/46
self-invalidation; filename-invariance sweep 46×109. 1,647 passed + 11
corpus-marked; gate GREEN byte-identical. R-3.5 confirmed empty (all §7
moves were in R-3.4). Findings, each pinned by strict xfail
(R4_CONFORMANCE_FINDINGS.md): **R4-1 HIGH** — first_farmers detects its own
corpus document only via the `<!-- SOURCE: filename -->` echo (gate coverage
partially resting on a filename); **R4-2 LOW** — relay scores a
filename-derived near-miss; **R4-3 MODERATE/HIGH-for-DSC-2** — six more
parsers (incl. chase: 618 discovery docs, wire-boilerplate exposure) detect
by a single bank-name marker, the R-3.4 defect class in parsers no corpus
doc mentions. Plus R-1 residuals: farmers_merchants matches customer name
ACE AUTO GLASS as an identity branch; altana/texas_bank digit runs.

**Ocean triage (R-4b, same session):** fix R4-1 now via a body-text issuer
marker (artifact text is the text of record); APPROVE the platform fix —
strip SOURCE comments in parser_registry, filename text structurally
inadmissible for all 46 — sequenced with R4-1's marker so the tree stays
green (closes R4-2 free); fix all six R4-3 parsers now under the R-3.4
marker standard, chase first; ADD the farmers_merchants customer-name branch
(R-1 zero-customer-names enforcement, guard-list addition); digit-run
residuals stay Wave-3 unless inside a guard already being rewritten; strict
xfails convert to passing assertions with their fixes. Acceptance: parity
109/109 · ambiguous 0 · cross-claims 0 · gate byte-identical · zero xfails
remaining for fixed findings.

---

## 2026-08-06 — H-3 Phase 2 REVIEWED: APPROVED; **MERGED to main as `1eeaeff` (ff), pushed; run 31134380538 dispatched**

Pipeline seam verified line-by-line: exactly the approved +18/−1 (one
import, one optional param, guarded callback, rationale comment against
Report.dispatch "simplification"). telemetry/ package; batch JSONL +
webapp SQLite v4 sinks; on-by-default with TELEMETRY_DISABLED; 38 new tests
incl. no-callback byte-identity on a real parse, sensitivity on three real
documents, JSONL/SQLite shape equality, T12. 1,261 tests in main checkout;
gate GREEN with the seam in play; corpus anchor: 109 claimed, deterministic
coverage 100%, validated 100 / review 6 / withheld 3 (the gate's three by
name), $0.0000 cost.

**Ocean acceptance of the ruling-5 correction:** gate-PASS ≠
corporate-use-validated — six documents reproduce all audited values AND
carry integrity flags (correctly `review`). The precise anchor (withheld
= the named 3, failed 0, validated+review = 106, coverage 1.0) asserts
the truth; the flat "106 validated" form is REJECTED as it would fold
review into validated and gut the class.

**Run 31134380538 (H-3 merge, `1eeaeff`): `completed success`** — third
consecutive fully green remote run.

---

## 2026-08-07 — R-4b REVIEWED: APPROVED; **R-4+R-4b MERGED as `fe4e958`, pushed** · **CI-2 RESOLVED** · DSC-1 dispatched

R-4b: all four findings fixed (first_farmers → issuer domain FFBT.COM from
the artifact body; SOURCE-comment strip central in the registry — filename
text structurally inadmissible for all 46; six R4-3 issuer-furniture
markers; ACE AUTO GLASS purged from TWO sites — the widened guard found a
second occurrence in the account_name regex — with layer-wide
removed-literals scan, classification_registry exempted by documented
design). 8 strict xfails → 0, each converted in its fix commit. New
permanent invariant: no registration identifies a bank by one marker alone
(documented exception: td_canada, layout probe). Parity 109/109 clean;
2,070-pair cross-product 0 cross-claims; 1,681 branch / **1,718 merged**
tests; gate GREEN byte-identical. Wave-3 log: altana digit run;
farmers_merchants as weakest-evidence registration (its corpus document
carries NO issuer identification at all — verified exhaustively).

**CI-2 RESOLVED AS TRANSIENT:** the fe4e958 push CREATED a run
(31134956413, event=push) — push triggers recovered on their own,
confirming GitHub-side event-delivery degradation over the billing
hypothesis. Gustavo's billing check no longer needed. Duplicate manual
dispatch cancelled; manual-dispatch protocol RETIRED (falls back only if
the anomaly recurs).

**Run 31134956413 (R-4b merge `fe4e958`, event=push): `completed success`**
— fourth consecutive green, and the first green run created by the normal
push lifecycle. CI is fully operational end-to-end with zero open items.

**DSC-1 DELIVERED and APPROVED (commit `a8e2ca7` on wave2-proof; merge held
for DSC-1b micro-task).** Dry-run acceptance: 109/109 enumerated+processed,
coverage 100%, validated 100 / review 6 / withheld 3 by name, 0 unexpected
dupes, expectations-file parity, gate GREEN, 1,741 tests. **Tranche-0
profile of the frozen archive (first real intake numbers):** 3,506 docs —
digital 3,297 (94.0%) / scanned 176 (5.0%) / unknown 17 / mixed 16; dedup:
124 within-archive duplicates + 82 copies of pinned corpus docs → ~3,300
unique; truncation 0; baseline byte-exact vs the freeze. Operational
implications: tranche 1 covers ~94% immediately; tranche 2 is only ~176
docs (D-4 concurrency likely unnecessary — decision data in hand). Three
runner findings fixed in place: case-insensitive manifest partition (a
`Scotiabank/` vs `ScotiaBank/` case-fold silently moved a pinned doc into
the discovery set under exact matching — recorded as `case_mismatches`);
cached rows excluded from the dispatch-coverage denominator (`--no-cache`
for full re-dispatch); folder-label mismatches classed `label_unmatched`
(abbreviations like BofA/Amex), never "disagree". **DSC-1b micro-task
dispatched:** `deferred` telemetry outcome class (explicitly declared,
never inferred) so `failed` unambiguously means attempted-and-errored
before any real tranche runs.

---

## 2026-08-07 — DSC-1b merged; **WAVE 2 BUILD CLOSED at `3d3a63f`, remotely green**

DSC-1+1b merged (`0b17099`, 1,745 tests); wave branches and worktrees
removed after ancestry verification (repo back to main + mt-lead); memory
and PROJECT_STATUS updated. One CI-only brittleness surfaced at close: the
no-model-client sandbox test compared full subprocess stdout to its
sentinel; the Linux runner prepends a harmless warning line (run
31137747002; 1,744/1,745 passed; the security property itself held). Fixed
as an Ocean unblocking spike (`3d3a63f`, last-line comparison, run cited).
**Run 31137938616 (push, `3d3a63f`): success — main remotely green at
HEAD.** Outstanding decisions: Gustavo's tranche-1 go; prototype-branch
deletion after P2-1. Wave-3 backlog seeds recorded in PROJECT_STATUS and
the roadmap memory.

**DSC-1 dispatch record (original bindings):** production
parse_statement only; frozen-baseline verification (3,768/3,615/
996,080,803) with loud-stop on deviation; pinned-manifest partition;
D-3 cache + H-3 telemetry consumption; tranche modes
(--profile-only/--digital/--scanned/--dry-run); dry-run acceptance =
109 enumerated / 0 unexpected dupes / expectations-file parser match /
ambiguous 0 / validated 100 · review 6 · withheld 3 / coverage 1.0;
no Gemini, no tranche-1/2 archive runs by the agent (operational phases
remain Ocean+Gustavo-gated).

**Critical DSC-1 input (from H-3's own harness mistake, disclosed):** the
generic `parse_native_pdf_text` silently produces DIFFERENT markdown than
the production ladder for four banks (Navy Federal, TD Canada, Wells,
Desjardins — layout-aware readers run first). **DSC-1 MUST resolve
documents through production `parse_statement` (OCR rungs disabled for the
offline dry run), never the generic reader.** Recorded as a DSC-1 design
requirement.

---

## 2026-08-06 — H-3 Phase 1 (schema) REVIEWED: APPROVED; Phase 2 GO

H3_SCHEMA.md (`3874e1a` on wave2-proof). Survey findings accepted: (1)
Dispatch carries claimants only — near-miss band comes from
`detection_report()`, admissible as run-of-record because detect is
pure/total by RFC contract; (2) score sparsity measured (~4 non-zero of 46
per doc) settles the vector question. **Ocean rulings:** 4-line `on_dispatch`
callback seam approved (no Report.dispatch — Dispatch.statement is the full
financial record; rationale to live in the module docstring); non-zero
scores best-first cap 12 + flag; cache-hit hole stays open by design
(`dispatch.source="cached"`, coverage still computable); sensitivity
invariant approved (no filenames, no extracted bank strings, exception class
names only — DSC-1 keeps its own gitignored hash→path map); outcome mapping
must reproduce the gate's 106/3 as a test; cost fields approved with
extraction-token capture as Wave-3 backlog; storage v4 + JSONL shape
equality + batch-no-webapp-import test; **telemetry default ON both paths**
with one documented env kill-switch (NullSink); retention append-only, expiry
deferred to D-7 with the trigger-conflict caveat recorded.

**Dispatches:** REEF → R-4 phase (six-parser fixtures, demo_national,
46-registration conformance harness, SOURCE-invariance check; tests-only;
any pipeline.py need = stop-and-ask). HARBOR → **H-3 Phase 1: schema design
only** (H3_SCHEMA.md, mandatory Ocean review before implementation; storage
= schema v4 + JSONL for batch; Dispatch object as data source; truncation
facts off the document object; cache_hit rows for freshness; sensitivity
invariant: hashes/ids/counts/timings, never customer data).

**D-3×O-3 integration gap confirmed as predicted** (put_ocr stores only
{model, pages}; page_integrity dropped on hit) → **D-3b dispatched to
Agent B**: round-trip page_integrity, bump OCR_STAGE_VERSION 1→2,
invalidation + round-trip tests.

**Remote gate first full execution (run 31128834443): suite step GREEN
(CI-1b works); gate step RED on adb_audit only — every drift line is the
`folder` metadata column pinned with Windows `\` vs Linux `/`. Zero
financial drift; balance_audit (POSIX paths) GREEN.** → **CI-1c dispatched
to Agent C**: separator-agnostic comparison for path-valued fields only,
with masking-prevention tests; no CSV edits, no oracle changes.

**Archive FROZEN (Gustavo confirmed complete; stability proven):** two
enumerations 12 min apart byte-identical — 3,768 files / 3,615 PDFs
(109 pinned + 3,506 discovery) / 996,080,803 bytes. This inventory is the
discovery corpus of record for DSC-1/DSC-2.

---

## 2026-08-06 — R-3 RFC — OCEAN RULINGS (all six questions)

1. **Score scale: APPROVED as specified** (0.0–1.0, CLAIM_THRESHOLD 0.5,
   computed required/corroborating formula). The decisive property is
   migration parity by construction. Scores are not cross-parser
   probabilities; calibration stays P2-9.
2. **§7.1/§7.2 literal moves: registration-based mechanism approved as
   primary, but LLM-path coverage is KEPT** — when no registration claimed
   the document, look up the registration by bank label (registry data, not a
   pipeline literal) and apply its `formal_statement`/`integrity_checks`.
   Today's semantics become a strict subset of the new behavior; nothing
   narrows. The lookup lives in the registry module, keyed off registration
   data.
3. **Ambiguous in `auto` mode: proposal APPROVED** — LLM extraction +
   `parser_ambiguous` integrity flag naming candidate ids + forced
   needs_review/manual_review_required. `auto` keeps its "always returns
   something" contract while approval stays fail-closed.
   `deterministic` mode raises `AmbiguousParserError` — approved.
4. **parser_expectations.json: APPROVED with audit-CSV authority** —
   generated once at R-3.0 against the unmodified chain, committed,
   regeneration is a deliberate Ocean-reviewed act (added to standing
   criteria). `tools/` may be created; REEF owns
   `tools/record_parser_expectations.py`.
5. **R-8 repairs: AGREED — named leftover.** One seam per wave.
6. **Six direct-untested parsers: R-4's detection-positive/negative
   synthetic fixtures for wells/scotia/columbia/navigant/relay/first_farmers
   are PULLED FORWARD, landing before R-3.4** (the pipeline switch — the
   moment of real risk). Full R-4 conformance harness still follows R-3.
   Also: report the measured full-registry detect-sweep cost per document
   (RFC risk 7) in the R-3 completion report. — REVIEWED: APPROVED; **MERGED to main as `91d5d92` (ff), pushed; verification run 31128834443 dispatched**

Drift proven before any edit (the 4 columbia tests pass unchanged on local
tesseract 5.5.0; runner runs 5.3.4 — the failure was detection-miss, "no
deterministic parser matched", not a wrong value; first_farmers cleared the
gap by luck and was converted too). Fix: scanned fixtures resolve through the
same pinned-artifact mechanism as the gate (`cached_markdown`, re-verified
against manifest pins on every read). Zero assertion values changed —
verified: removed lines are nine lines of source selection. New permanent
tests: artifact-pin chain equality (default suite) and live-tesseract
reproduction (opt-in `live`, skipif-no-binary). 803 passed / 4 deselected.
Exactly 2 files changed. **Ocean ruling:** widened `live` marker semantics
accepted ("runs real OCR rather than a committed fixture", documented); a
dedicated `tesseract` marker isn't worth the pytest.ini churn.

**CI-2 hypothesis from Agent C's API survey (unverified, checkable by
Gustavo in one click):** every run reports `billable.UBUNTU.total_ms = 0` on
a private repo where minutes must be metered — if run attribution to the
Actions entitlement is broken/exhausted, entitlement checks gate *creation*
of webhook-triggered runs while `workflow_dispatch` (direct authenticated
user action) bypasses. Consistent with all observations. **Operator check:
Settings → Billing and plans → Plans and usage → Actions minutes** (exhausted
+ $0 spending limit would confirm; a blocking banner would appear on the
Actions tab). Push-event delivery itself is confirmed working.

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
