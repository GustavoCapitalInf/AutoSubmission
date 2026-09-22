# Phase 2 remainder — resume handoff (2026-09-17 late, root/Ocean)

Supersedes `PHASE2-REMAINDER-RESUME-20260917.md` for the step-05/06 thread. Everything else in that
document (constraints, privacy boundary, endpoint rules, the sealed batch, cost ownership, Phase 3
exclusion, the user-owned uncommitted plan and `docs/moneythumb-replacement/superpowers/`) stays in
force unchanged. Nothing here launches a GPU job, publishes, merges, pushes, tags or asserts completion.

## FREEZE POINT — 2026-09-17 (Gustavo's instruction: Phase 2.3 deferred and resumable, Phase 3 unlocked for planning only)

* **Status of Phase 2/v6:** COMPLETE through step 6 (the v6 family), DEFERRED beyond it. Not abandoned,
  not implicitly completed, not disposed. The orientation family (steps 7–12), the compiler/reader
  successors, the B bridge, V docs and final validation are deferred exactly as described in §0/§4.
* **Git checkpoint:** branch `train13`; the freeze commit carries only root-authored documents (this
  handoff, the canonical handoff pointer, `PHASE2_RULINGS.md` R15, the Phase 3 proposal) and is tagged
  `phase2-v6-freeze-20260917` (local tag, not pushed). Gustavo's own uncommitted edits
  (`docs/moneythumb-replacement/phase2_remainder/PHASE2_REMAINDER_PLAN.md`, 86 added lines, and the
  untracked `docs/moneythumb-replacement/superpowers/` notes) are deliberately NOT committed; their
  bytes are preserved as a patch and copies in the checkpoint directory below.
* **Checkpoint directory (private, gitignored):**
  `discovery_reports/train13-logs/checkpoints/phase2-v6-freeze-20260917/` holding `git-state.txt`
  (branch, HEAD, status), `uncommitted-tracked.patch` (the owner's plan diff and any other tracked
  diff at freeze time), `untracked/` (byte copies of every untracked project file), `memory/` (copies
  of the auto-memory files), `MANIFEST.json` (SHA-256 of every preserved artifact: the campaign
  receipts of steps 1–6, the segment and reinspection windows, the four instrument packages, the
  frozen descriptors, design notes and reviews, the ledger, the tracked documents at freeze bytes) and
  `CHECKPOINT-README.md` (restoration and resume procedure). The manifest's own SHA-256 is recorded in
  the ledger and in the README.
* **Restoration:** `git checkout train13 && git verify-tag phase2-v6-freeze-20260917 || git tag -v …`
  (or simply `git checkout phase2-v6-freeze-20260917`); re-apply the owner's plan edit only if it is
  no longer in the working tree (`git apply --check` then `git apply` of `uncommitted-tracked.patch`);
  copy back any missing untracked file from `untracked/`; verify every artifact against
  `MANIFEST.json` (`python -c` one-liner in the README). Worktrees: `mt23-v6-v2` must be clean at
  ff633a6c…, `mt23-orient-v2` clean at 973af29…; the campaign store must match the manifest.
* **Resume Phase 2.3 / orientation later:** read this file top to bottom, then §4 (the orientation
  design note is a proposal; the recovery package holds byte copies only). No command in §4 has been
  run beyond item 4c (stage 6). The next command is the orientation design review, or the compiler
  successor for the v6 comparison report; both start from the ledger's last entry.
* **After this freeze, no change is made to any Phase 2/v6 instrument, receipt, descriptor or window.**

## 0. Update 2026-09-17 20:20Z — the v6 family is complete; direction is Gustavo's

* Gustavo ruled (R15): 38/48 with the six double reads flagged. Joined v2 frozen (5421d860…), D1R2
  frozen (510f8815…, 211 inputs), **stage 6 closed** (80 attempted, 78 evidence, 2 refused; result
  67049fbb…; partition-key guard and same-host anchor equal; chain validated under D1R2). Steps 1–6 are
  done. Do not rerun anything in `campaign-v6-first-01`.
* The orientation family (steps 7–12) is ON HOLD: Gustavo stopped its design review. The design note
  `p23config-prep/ORIENTATION-RECOVERY-CHAIN-DESIGN-ROOT.md` is a proposal; the package directory
  `orientation-recovery-source-01` holds byte copies only, nothing pinned, reviewed or run.
* Phase 3 is UNLOCKED FOR PLANNING ONLY (Gustavo, 2026-09-17: no implementation, training, data
  export, paid compute or production integration). Proposal v0: `docs/moneythumb-replacement/phase3/
  CI-STATEMENT-VLM-PLAN.md` (preserved). Program plan v1 (the governing draft, 23 sections incl. the
  language/performance study, licensing review, two-week ceiling experiment and the five owner
  decisions): `docs/moneythumb-replacement/phase3/PHASE3-VLM-PROGRAM-PLAN-v1.md`. Nothing in it
  executes until Gustavo approves the ceiling-experiment budget (its section 21).
* Root's process assessment (ledger, 2026-09-17): ceremony out of proportion to evidence; fix the cache
  partition key's environment dependence at the root; one generic step instrument instead of a package
  per interruption; review scaled to risk; half-day time box per recovery; reorder toward the layout
  model and admission. Section 1 below is now historical (the decision was taken).

## 1. One decision waited on Gustavo (RESOLVED 2026-09-17: option B, R15)

The independent design review required this to be surfaced before the joined disposition v2 is
frozen, because it moves the reported primary V6 denominator. Its exact wording:

> "Six of the 48 V6-U755 documents were read twice by the same pinned paddle-v6 pipeline — once in
> the paired stage on the retired host, once in the continuation segment on the replacement host —
> with byte-identical page rasters and a different cache partition key. Do we report the primary
> stage as 38/48 using the segment readings with the six flagged as double reads (root's
> recommendation), or as 32/48 excluding them?"

Root's recommendation is **B: 38/48 with the six flagged** (`primary=segment; paired=step-02;
double_read surfaced`). Option A is `primary=exclude; paired=step-02; double_read unqualified`
(32/48). Both options use the same instruments and the same reinspection; only the explicit
`--compilation-rule` argument of `freeze_joined_disposition.py` differs, and both numbers are
reported under either rule (`qualified_primary_documents`, `primary_documents_without_double_reads`).
Until the ruling: do NOT run `freeze_joined_disposition.py`, `prepare_successor_descriptor.py` or
`step06_window.py`.

## 2. What happened on 2026-09-17 (receipts in `discovery_reports/train13-logs/`, ledger `ROOT-RESUME-20260916.md`)

1. Replacement Vast endpoint configured privately and proven ready (`endpoint-closure-01`); model-asset
   ledger hashes differ across hosts because the pinned worker hashes hub download metadata
   (recorded, not a refusal; same-host equality against the readiness worker record is required).
2. Continuation package reviewed (MAJOR-1..4 closed, minors 15–18 recorded), proof `closure-04`
   green, scope authority frozen (e2ce9980…), **D1R frozen** (f7e5f30d…, 156 inputs).
3. **Segment `step-05-continuation-01` ran** (17:00:29Z–17:13:13Z): child COMPLETE (38 attempted, 36
   evidence, 2 refused, attestation passed, original ten untouched), but the in-process inspection
   REFUSED `paired_cache_reuse_changed`: six PAIR-V6 members inside the remaining 38 were re-read
   fresh under a different cache partition key. `result.json` is `failed`, immutable. The window is
   attempted; **never relaunch it** (`segment_already_attempted`, doctrine).
4. Cause: the OCR settings key hashes environment-derived material (OCR service description and
   PATH-resolved tool versions besides the static Paddle block); it changed between the original
   dispatch and today's launch; the exact variable is not recoverable from receipts. The six pairs have
   byte-identical ordered page rasters (6/6), `rasters_mismatched 0`, identical pinned runtime identity;
   steps 02–04 preserved files all intact; nothing overwritten. PAIR-V6 ∩ V6-SLICE = 0.
5. Disposition designed (`p23config-prep/STEP05-DOUBLE-READ-DISPOSITION-DESIGN-ROOT.md` + Amendments
   1–3 and "Live outcome"), independently reviewed (`…-DESIGN-REVIEW-X.md`, 71780abe…,
   APPROVE-WITH-CHANGES, all thirteen changes applied), implemented as ONE package
   `p23config-prep/v6-step05-v2-source-01/` (22 files, FINAL manifest
   d81cae7ac27bbee111b0925efb60128f68f2272fb5dc91fcf2302f96b379d4c1), 36/36 tests green directly and
   under the audited proof `live-proof-closure-03` (result 63a5373f…, zero boundary denials).
   Independent source review `V2-SOURCE-REVIEW-X.md` (06d666d8…): two REQUEST-CHANGES rounds
   (unbound provenance key; pre-flight sink inside the window), all closed; re-review 3
   APPROVE-WITH-MINORS (S1–S4 deferred to the D2/orientation package, recorded in the ledger).
6. **The read-only reinspection RAN** (19:15:34Z–19:15:48Z, lock held, no child, no remote request):
   COMPLETE. Window `step-05-continuation-01-reinspection-01` (+ sibling `-import-sink`): 36 evidence,
   2 refused, expected overlap 6, all six classified `double_read` (none cached, refused or unread),
   same-host reference equal, cross-host driver/ledger differences recorded, observation byte-identical
   to the refused first inspection's, inventory unchanged. Receipts: result ffffec36…, release
   9ce824d8…, inspection c9960272…, launch 513e3dc8…, observation db30bf35….
7. `freeze_joined_disposition.py --check-only` is VALID under both compilation rules (38 attempted /
   36 evidence / 2 refused; 6 double reads; producer D1R). Nothing frozen.

## 3. Required reading (in order)

1. `docs/moneythumb-replacement/phase2_remainder/PHASE2_REMAINDER_PLAN.md` (user-owned uncommitted
   edit; do not overwrite or restore), `docs/moneythumb-replacement/PHASE2_RULINGS.md` (STOP list),
   `PHASE2-REMAINDER-RESUME-20260917.md` (constraints, endpoint, privacy).
2. `discovery_reports/train13-logs/ROOT-RESUME-20260916.md` (tail: every receipt hash of the day).
3. The design note + Amendment 1, the design review, the package `SOURCE-HANDOFF-ROOT.md` and
   `V2-SOURCE-REVIEW-X.md`, `STEP05-CONSUMER-ACCOUNTING-DESIGN-ROOT.md` (amendments a/b).
4. The segment window's `result.json`, `release.json`, `segment-execution.private.json` (technical).

## 4. Ordered next actions

1. Recheck worktrees (`mt23-v6-v2` clean at ff633), process/lock state (`HARNESS.lock` absent),
   the replacement endpoint (`tools.paddle_vast check --config paddle-v6` at ff633 with `ocr.config`
   imported first). Preserve user edits.
2. DONE 2026-09-17: source review closed at manifest d81cae7a…, proof closure-03 green, the
   read-only reinspection complete (§2 items 5–7). Do not rerun any of them; the reinspection window
   is single-shot (`reinspection_already_attempted`).
3. Surface §1 to Gustavo (this document). STOP automatic advancement here.
4. After the ruling, from `discovery_reports/train13-logs/p23config-prep/v6-step05-v2-source-01/`
   with `C:\Python314\python.exe -B` (S5 = `../v6-step05-continuation-source-01`):
   a. `freeze_joined_disposition.py --out <v2>/v6-step05-joined-disposition-v2.private.json
      --scope-authority <S5>/v6-step05-aborted-scope-v1.private.json --scope-authority-sha256
      e2ce9980f84ec53dbb391ba5c07ba819eb4276edbb2bb06e093ea3273e617eb6 --descriptor
      <S5>/live-descriptor-continuation-01.private.json --descriptor-sha256
      f7e5f30d3a31164c71fa4b2b3053160c841c7c23ee90aa6388c5854e3ac37c8e --compilation-rule "<ruled
      rule literal>"` (the two literals are `primary=segment; paired=step-02; double_read surfaced` and
      `primary=exclude; paired=step-02; double_read unqualified`). Read the frozen document; record its
      hash.
   b. `prepare_successor_descriptor.py --out <v2>/live-descriptor-successor-01.private.json
      --source-pins-sha256 d81cae7ac27bbee111b0925efb60128f68f2272fb5dc91fcf2302f96b379d4c1
      --proof-sha256 63a5373f3b50ac9c51a6a2755a09b74586817e3766b1cd65d7d144b570d34033 --proof-label
      closure-03 --joined-disposition <v2>/v6-step05-joined-disposition-v2.private.json
      --joined-disposition-sha256 <from a> --source-review <v2>/V2-SOURCE-REVIEW-X.md
      --source-review-sha256 06d666d888d9dd68a586b3322fad72cb0c4852b3c9fd60d89f25858b3eb72bf8
      --design-sha256 <current sha of STEP05-DOUBLE-READ-DISPOSITION-DESIGN-ROOT.md> --design-review-sha256
      71780abe06c3e6b3d9d8977ca82ef6069d3096b8445148c9b3a5f11f8deb4f3e` (D1R2; inherits all 156 D1R
      inputs, adds the v2 package, joined v2, reinspection/segment receipts, design + reviews + proof).
   c. Recheck lock/tree/endpoint, then `step06_window.py --descriptor <D1R2> --expected-sha256 <sha>
      --joined-disposition <v2>/v6-step05-joined-disposition-v2.private.json --joined-disposition-sha256
      <sha> --instrument-pins <v2>/source-pins-01.json --instrument-pins-sha256 d81cae7a…
      --source-review <v2>/V2-SOURCE-REVIEW-X.md --source-review-sha256 06d666d8… --proof-result
      <v2>/live-proof-closure-03/result.json --proof-result-sha256 63a5373f…` detached (PowerShell
      Start-Process with quoted arguments; ~40 min for 80 documents). The key-material pre-dispatch
      guard must show the segment's partition key (`37027D7B…`); a refusal
      `cache_partition_changed_since_segment` means STOP and investigate, never override.
6. Orientation family: D2 must carry the amended overlap rule, the launch-time key-material receipt and
   the paired-overlap canary chunk ordering (design review MAJOR-8) BEFORE stages 7–12; readiness at
   the 973 tree for `paddle-v5-prod`/`paddle-v5-orient` still owed.
7. Compiler/reader successors per the consumer accounting note (binding-driven resolution, dual 38/32
   metric, six-pair content diagnostic), B bridge, orientation blind probe, V docs/privacy/composition,
   final validation; then 2.4–2.7. Unseen batch stays sealed.

## 5. Standing constraints (unchanged, restated)

No re-dispatch or ordinary resume of any closed window; the original ten stay `dispatched_unqualified`;
one heavy window at a time under `HARNESS.lock` (non-queueing, released by its owner only); winrun
floor 1.5 GiB / cap 4 GiB; opt-in literals only in a run's own environment; connection configuration
only in the gitignored `.env`; no customer content, financial values, document identifiers beside
verdicts, credentials or raw logs in ordinary output or Git; Unlimited OCR on a different computer;
cost is Gustavo's; Phase 3 excluded. Bash-tool heredocs mangle backslashes and choke on some
contents: write Python and Markdown through the file tools.
