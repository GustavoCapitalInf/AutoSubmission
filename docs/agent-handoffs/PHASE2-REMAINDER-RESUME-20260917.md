# Phase 2 remainder — handoff for the next agent

**Prepared 2026-09-17 at Gustavo's request. Read this before resuming.** This is
the current restart guide; older handoff snapshots remain historical evidence.
The user requested a handoff before further execution. No live work was resumed
while preparing this document.

## 1. Outcome and immediate restart point

**Phase 2.2 is complete. Phase 2.3 is partially complete. The approved bounded
VL-1.6 versus v5 comparison is complete. Phase 2.4–2.7 remain unimplemented as
milestones. The unseen batch remains sealed.** No production extractor switch
or experimental coverage gain has been admitted.

The last live operation was configuration-study stage 5, which failed after its
first ten-document chunk because the post-chunk worker identity request could
not connect. Preserve that failure. A reviewed recovery design processes only
the remaining 38 documents; its implementation and proofs are still owed.
**Do not rerun the original stage-5 command or ordinary wave resume.**

Gustavo has now supplied a **replacement Vast GPU**, described as the same
configuration. Its exact connection and public key are saved locally in the
ignored file `discovery_reports/train13-logs/p23config-prep/NEW-VAST-ENDPOINT-20260917.private.md`.
It has not been configured or tested by this handoff. Historical endpoint
descriptors must remain immutable; bind the new endpoint/session separately.

At handoff inspection, `HARNESS.lock` was absent and no local Python/SSH process
was returned by the process-name check. Recheck actual processes and ownership
before launching anything; this is a snapshot, not permission to remove locks.

## 2. Required reading and authority

1. [The user's Phase 2 remainder plan](../moneythumb-replacement/phase2_remainder/PHASE2_REMAINDER_PLAN.md), especially the approved amendment near its start and **§G.2.3A**.
2. [PHASE2_RULINGS.md](../moneythumb-replacement/PHASE2_RULINGS.md): later rulings supersede older proposed plan wording. In particular, Unlimited OCR must run on a **different computer**, not this Vast Paddle instance; cost/billing is the user's responsibility.
3. [PHASE2_ARCHITECTURE_PLAN.md](../moneythumb-replacement/PHASE2_ARCHITECTURE_PLAN.md), [BATCH9-RULES.md](BATCH9-RULES.md), [PHASE2-RULES.md](PHASE2-RULES.md), and [ORCHESTRATION-MODEL-POLICY.md](ORCHESTRATION-MODEL-POLICY.md).
4. [PHASE2-3-WAVE.md](PHASE2-3-WAVE.md), [P23-CONFIG.md](P23-CONFIG.md), and [P23-FALLOUT.md](P23-FALLOUT.md).
5. [PROJECT_STATUS.md](../moneythumb-replacement/PROJECT_STATUS.md), [PHASE2_STATE.md](../moneythumb-replacement/PHASE2_STATE.md), and the older [handoff](PHASE2-REMAINDER-HANDOFF.md) for supporting history.
6. Local execution ledger: `discovery_reports/train13-logs/ROOT-RESUME-20260916.md`. Its latest entries supersede earlier active-process snapshots. Read actual receipts before relying on a summary.

The working plan's handoff-time SHA-256 is
`d5dd8e947b4d37c713dbd30f5af041e2999e3685092b578298d96b2cb1365ebc`.
It is a **user-owned uncommitted edit**. Do not overwrite it or restore its older
Git version. `docs/moneythumb-replacement/superpowers/` is also user-owned and
untracked. Neither was staged by this handoff.

Standing authorization covers continuing Phase 2 through 2.7 on green gates;
Phase 3 is excluded. Preserve the rulings' stop conditions and publication gates.
The user already approved the configured Paddle path and the fifth legacy repair
fence with zero-change verification. Do not ask for those approvals again.

## 3. What has been implemented

| Plan milestone/cell | Implemented and measured | Still required |
| --- | --- | --- |
| **2.2 — truth instruments** | Completed before this continuation: identity/provenance, classification and truth instruments, precision controls, holdout cage. | Preserve existing closure; do not rebuild or reopen its sealed inputs. |
| **2.3 W — wave runner** | Reviewed resumable research runner, lifecycle/identity/retention, custody, retained rasters, technical telemetry. Original production CTRL/U755/SLICE runs closed. | Configuration-study recovery and remaining alternative runs below. |
| **2.3 E — extraction quality** | Reviewed quality metrics/censuses and admission guards; composed with W/X. | Final configuration comparison and composed validation. |
| **2.3 X — agreement** | Reviewed native/Paddle agreement and census instruments; composed with W/E. | Final per-configuration measurements. |
| **2.3 B — baseline fallout** | Cache-only existing-structurer analysis, per-source funnel, blind control probe, truth-v2 and slice-2 queue. Original production scope independently approved. | Three alternative cohorts, qualified-input gate, report bridge, orientation CTRL blind probe, any resulting additive queue disposition. |
| **2.3 P — precision** | Five legacy repair callers fenced, including approved Truist fence; original function definitions retained. Replay: 2,695 identical; classifier 3,380 identical with 372 explicit exceptions; 82 mutants; independent closure/privacy review. | Compose P with V/B and run required final composed checks. |
| **2.3 V — configuration A/B** | Three pinned configuration blocks, explicit identity/key/provenance separation, production unchanged, comparator and guards; synthetic/backend proofs; four paired v5/v6 readings closed. | Interrupted primary stage 5, stages 6–12, actual comparisons, downstream B work, final docs/scans/floors/composition. |
| **2.3A — bounded VL-1.6** | Completed and independently reviewed; report below. | Feed its limitations into 2.4/2.5/2.6. No additional VL work is needed to repeat this experiment. |
| **2.4 — generalized reconstruction v1** | Not started as a milestone. Existing geometry/structurer code is baseline infrastructure, not completion of this plan. | LayoutModel, neutral structurer v2, archetypes/mutations, wiring, fallout v3, frozen-design unseen evaluation and admitted native gains under the plan. |
| **2.5 — reconstruction v2 / Paddle admission** | Not started. | Harden from measured residue, evidence-supported pre-financial triggers, page routing, disagreement review, lineage, fallout v4 and admission proofs. |
| **2.6 — Unlimited OCR** | Not started. VL-1.6 work does not implement this milestone. | Evidence-based go/no-go, separate-computer contract/proof and conditional integration; no-go/deferred is valid under its gate. |
| **2.7 — final closure** | Not started. | Routing freeze, exact censuses/denominators, holdout/reporting, runbooks/parity, full floor/cold/CI and release requirements, Phase 3 handoff only. |

W/E/X are composed on the train at `b4fe66711c6745c32ca72e45b7ce730e7c493d65`.
**V/B/P are not finally composed on the train.** Reviewed branch code and private
proofs do not equal final milestone closure.

Fourteen V production replay windows and their accountant are complete:
**2,695 evaluated documents identical, including all 2,625 validated documents**;
685 outside that union remain unmeasured. Accountant:
`PREP/production-accounted-closure-01/summary.json`, SHA
`a486954073a2065159811ee4ea32b33b0a167c095c2b768730c97119fdebbbb6`.
Do not rerun those original windows merely because the session changed. Final
combined-source validation is separate. An earlier full suite had 10,440 passes
and two failures later handled by focused recovery; do not report a later whole
suite as green without running it at the required final scope.

## 4. Completed VL comparison — result and limits

Read [VL16_V5_COMPARISON_REPORT.md](../moneythumb-replacement/phase2_remainder/VL16_V5_COMPARISON_REPORT.md),
SHA `3d09d1ec1bc6fda246ef9134e03e5f13e045c371f9255d85bf43a779ee540d10`.

- All 32 synthetic calls have dispositions. Development: 84 requested page slots, 18 gated, 66 attempted, 65 responses, 59 accepted observations and seven refusals; no eligible slot remains unattempted.
- Only **one printed amount on one scanned page**, repeated twice, was commonly measurable under the frozen rules. VL recovered its literal; v5 did not. Both preserved its sign. No broad model ranking follows.
- Each model reproduced its defined evidence for 12 measurable repeat pages, but cohorts and equality definitions differ. Raw-response equality is a separate question.
- VL supplies region geometry; it does not satisfy the current word-box consumer. Rows, complete-page fidelity and downstream false accepts remain unmeasured.
- Recommendation: retain v5 production and investigate VL separately if later justified. No automatic integration or admitted gain.
- Preserve the report's audit/transport/cleanup limitations. Later custody checks did not retroactively make failed runs successful.

Lossless SSH compression was enabled in prior work. A two-tunnel experiment did
not establish a speedup; do not raise OCR concurrency. The earlier 33-hour estimate
was for full populations, not this remaining continuation. No reliable estimate
has been established for the replacement GPU.

## 5. Repository and source versions

Repository root is the current `bankStatementAnalysis` workspace. Python is
`C:\Python314\python.exe`; shell is PowerShell. In this document:

- `PREP` = `discovery_reports/train13-logs/p23config-prep`
- `LIVE` = `discovery_reports/train13-logs/p23config-live/campaign-v6-first-01`
- Worktree names below are under `.claude/worktrees/`.

| Worktree / role | Exact tip | Status |
| --- | --- | --- |
| Root `train13` before this handoff commit | `485fbcde47ea5e2dc7a7324a3810b2ec77784490` | Latest code/progress snapshot; only user plan/superpowers were dirty. |
| `mt23-config` | `d5dc8fae11e7a8171a48c4b82af4eefc43c521e0` | Historical V source; preserve. |
| `mt23-v6-v2` | `ff633a6c23ec1d4ceb81a75a9d4999f46f29535e` | Actual stages 1–5 producer; study-label digit fix. |
| `mt23-orient-v2` | `973af29ef1ac8299cfc4850a2a055eef0c165235` | Reviewed orientation class-0 handling and synthetic compatibility. |
| `mt23-comparison-v2` | `de420c933d018601f7147808bbcf01f12ec76162` | Comparator with strict UTF-8 population-comment handling. |
| `mt23-config-final-v2` | `1b2c2c6c0f390ee1701802fed6419de31bdb554e` | Reviewed source union of V fixes; not final runtime/floor closure. |
| `mt23-fallout` | `403f231641ddee11d087fa5f68f7b658fa4bcc32` | Independently approved B closure; actual analysis producer was `9fd45077a553c53eabdc25b629d6fb5da5e06c08`. |
| `mt23-precision` | `778be7f9ea0b3a6e59c188e7ae9c5fece6a11374` | Independently approved five-fence P closure. |
| `mt23-vb-source-v1` | `debbd0f65547c309eded69dd0b1407c9c6537f28` | Isolated V+B source preparation only; independent composition review/floor pending. |

The last tree cherry-picks B onto `1b2c`. One OQ2 roots conflict was resolved by
retaining both lists. Root verified 27 V-only and 14 B-only blobs exactly; two
shared test files retain both additions. Analysis/layout/evidence match B403.
See `PREP/VB-SOURCE-COMPOSITION-ROOT-01.md`. Do not mistake this for final train
composition or a validated new producer.

## 6. Frozen twelve-stage configuration campaign

Membership is frozen in `PREP/study-manifests-compile-01`; selection rationale is
`PREP/ROOT-STUDY-SELECTION-DISPOSITION.md`. Unique union: 311 documents / 1,626
known pages. Stage counts overlap. V6-U755 represents 48 of 87 eligible strata;
39 were omitted. Sixteen unknown-profile/page U755 members remain disclosed in
the parent denominator. Do not retune membership from outcomes.

| Stage | Configuration / population | Store | Status |
| --- | --- | --- | --- |
| 1 | Production v5, PAIR-V6 first (8 docs / 20 pages) | fresh v6-1 | Child succeeded; inspector failed on legitimate excluded rows. Separately qualified offline; original failure retained. |
| 2 | v6, PAIR-V6 first | fresh v6-2 | Closed successfully. |
| 3 | v6, PAIR-V6 second | fresh v6-3 | Closed successfully. |
| 4 | Production v5, PAIR-V6 second | fresh v6-4 | Closed successfully. |
| 5 | v6, V6-U755 primary (48 / 220) | reuse v6-2 | Failed after dispatched first10; remaining38 not run. |
| 6 | v6, V6-SLICE primary (80 / 626) | reuse v6-2 | Unrun; needs reviewed stage5 disposition gate. |
| 7 | Production v5, PAIR-ORIENT first (8 / 18) | fresh orientation-1 | Unrun. |
| 8 | Orientation, PAIR-ORIENT first | fresh orientation-2 | Unrun. |
| 9 | Orientation, PAIR-ORIENT second | fresh orientation-3 | Unrun. |
| 10 | Production v5, PAIR-ORIENT second | fresh orientation-4 | Unrun. |
| 11 | Orientation, ORIENT-CTRL primary (36 / 218) | reuse orientation-2 | Unrun. |
| 12 | Orientation, ORIENT-U755 primary (156 / 597) | reuse orientation-2 | Unrun. |

Each closed paired reading has seven evidence documents / 17 pages and one
refusal / three pages. Equal counts establish no evidence equality or accuracy.
Do not redo these four readings. Match actual runtime/host/conditions before
comparing timings, particularly after the new GPU replacement.

Original D0 descriptor: `PREP/v6-first-source-03/live-descriptor-v6-first-05.private.json`,
SHA `2a097aeb4c74da612575d92dbee2f58cb8ba3a6ebe8ddc7182f3e6177890a550`.
D1 continuation: `PREP/v6-qualified-continuation-source-01/live-descriptor-qualified-01.private.json`,
SHA `2949f86e1c1c91868ee68551d1cbc56261839336225a1436c5ff7a17104ff133`.
D1 binds 87 inputs; its focused 14-control proof passed. Preserve both.

Original stage1 offline qualification is at
`PREP/v6-custody-recovery-source-01/step01-qualification-closure-02`; qualification SHA
`e288068564a239ce67a18d9b7adea4db6d7e811ecdd49fa70f36516c5ceacee3`.
All 654 source/input files were unchanged and no new OCR ran. This inspector-only
exception **does not qualify stage5's missing worker identity check**.

## 7. Stage 5 failure and reviewed recovery design

Original window: `LIVE/step-05`. Closed 2026-09-17 02:01:43 UTC, 816.6 seconds,
818.6 MiB peak job memory, no timeout. Parent child exit1 / controller2 / owned
release0. Actual retention and cleanup passed, with no worker/PID/request artifacts.

| Receipt | SHA-256 |
| --- | --- |
| `result.json` | `270726f328aabebfc75a162e1791ef54ced5550613d7e28d44958cf7eeead2a5` |
| `release.json` | `dfd5c1b89acfda2aa87c63e9c020c0c0e9beae46f8aaa9821a6c5dcc934af5d5` |
| `resources.jsonl` | `5f0c0e1bd66a700478a703909e6d654db8b3b296ee568b10fdfd159628698f55` |

`wave._run_one_chunk` called discovery, then failed its mandatory GET `/version`
check before inspecting the nested return code, retaining rasters, or publishing
outcomes. The nested return code was not persisted. Original wave state is empty
apart from its ended session; this does not mean no requests ran.

Finite metadata projection: `PREP/step05-technical-projection-root-02.json`, SHA
`2e4cbd547452bb18d74308ac2a567d700c4526e0e52840a27d21f27e6ce22d02`.
It binds the five original files, unchanged before/after: one chunk of ten,
one custody run, ten unique selected rows, 51 known row pages, one cache hit/nine
misses, seven Paddle research rows/three failed Paddle rows, seven artifact
bindings with zero unbound reads. All 3,496 outside rows satisfy the strict
14-field skipped signature, including all remaining38. U755/SLICE are disjoint.
These are custody facts, not qualified model measurements or wire-request counts.

Read these complete local design files:

- `PREP/STEP05-CONTINUATION-DESIGN-P.md`, SHA `539d55839443a6f7baef3c1603b48f2226cf5681f6c201e08bcc9726fd6ed698`.
- `PREP/STEP05-CONTINUATION-DESIGN-REVIEW-X.md`, SHA `90e62e19e6c56f1cccfd06cffeeb3c9871814edf527e6e06173ab9f64a9f53db` — independent approval of **source preparation**, not execution.

Agreed approach: quarantine all original10 as `dispatched_unqualified`; process
only full48 minus dispatched10. Reuse actual `_run_one_chunk` and Lifecycle in a
private executor, fresh segment state, append-only chunk indices1–4, preserving
original chunk0/state/run/receipts byte-for-byte. Retain nested dispatch/results
before the unchanged post-check. No guard monkeypatch or invented WaveState rows.
Step6 needs an explicit joined-disposition preflight. D1R, orientation chain,
compiler and reader need narrow successors; first10 stay unqualified/unmeasured,
never silently called unattempted or filled from raw cache/native/paired evidence.

**Implementation status at handoff:** proposed directory
`PREP/v6-step05-continuation-source-01` was absent. No continuation source package,
initial scope authority, D1R, customer retry or reader successor was completed.
Root had authorized source preparation before the usage interruption. Resume
implementation from the reviewed design, not from a presumed runnable package.

The final proposed initial authority schema is preserved in the local checkpoint
append made with this handoff. It has 19 exact file-binding roles and explicit
48/10/38 sets; do not use placeholder hashes or fabricate future closure.

## 8. Offline comparison and orientation readiness

- Orientation class0 handling at `973af29` passed 81 focused tests, upstream cases/refusals/mutations, and two actual synthetic compatibility observations (upright and rotated180, each 54 words / 10 lines). Coordinates remain approximate upstream boxes; no localization-accuracy claim. The replacement GPU needs its own actual readiness/session check.
- `PREP/orientation-customer-source-01`: nine transition controls passed; actual D2 descriptor has **not** been frozen. Its old transition expects ordinary closed stage6 and must be adapted to the reviewed recovery chain.
- `PREP/comparison-v6-first-source-01`: eight compiler controls plus tracked decoder control passed in `comparison-input-proof-closure-02`. First failed proof retained. Actual all-twelve input compilation has not run.
- `PREP/comparison-execution-source-01`: wrapper v3 and seven controls passed in `comparison-execution-proof-closure-01`; outer SHA `c496b38cccd01c5a2539a517294915d188a638b69a0d004d82e6972d61268d15`. Independent review is `COMPARISON-EXECUTION-PROOF-CLOSURE01-REVIEW-X.md`. These prove the **old strict chain schema**, not the unfinished stage5 successor.
- Actual comparator timeout is 3,600 seconds; compiler/proof bounds remain 600. This is headroom, not a forecast. Run one family/window at a time after all stage dispositions and actual compilation close.
- Original historical/native source mapping is ready: `HISTORICAL-NATIVE-AUTHORITY-MAPPING-X.md`, `HISTORICAL-NATIVE-AUTHORITY-JOIN-X.md`, and `historical-comparison-metadata-root-01.json` in PREP. Use original TRAIN12 native provenance and the fifteen historical CTRL/U755/SLICE runs. Do not discover newer keys or replace missing readings.

Final authority/consumer changes must preserve all failed statuses and original
producer tips, include the exact interrupted segment, and pass actual compiler-to-
reader fixture tests. Existing old-schema proofs are not invalidated historically,
but cannot stand in for the changed path. Metrics and sample selection stay fixed.

## 9. Remaining alternative B work

The three explicit overlaps are ORIENT-CTRL36, ORIENT-U755156, V6-U75548.
SLICE remains mandatory for V's OCR comparison; its downstream B funnel is outside
the current CTRL/U755 schema and explicitly unmeasured. Do not rename SLICE.

Read PREP files:

- `V-ALTERNATIVE-B-FALLOUT-SCOPE-ASSESSMENT-X.md`
- `ROOT-V-ALTERNATIVE-B-SCOPE-ADOPTION.md`
- `V-ALTERNATIVE-B-REPORTING-BRIDGE-DESIGN-X.md` (SHA `8b69f266a8eb251b79d29bce4c918570ae2de72e4ed9656ee4e2df5486c4199e`)
- `ROOT-B-REPORTING-BRIDGE-DESIGN-ADOPTION.md`

Reuse old native/Tesseract baseline rows at actual producer9fd. New alternative
analysis must use qualified immutable OCR sources, existing structurer/validator,
zero OCR/network, and a fresh analysis sink. Existing B reporter enforces one
producer commit, so validate each producer separately and apply unchanged
`paddle_helped` to the exact provenance-selected baseline. Never rewrite old
source commits, select a baseline by verdict, or rerun closed production B.

There is one **unfinished, unreviewed, untested draft**:
`PREP/b-fallout-bridge-source-01/b_fallout_reporting_bridge.py`, handoff SHA
`de74c24fde4c6456fd906a92158d2975effa372484d4157d88533b65fc9b6e90`.
No fixture tests or frozen source manifest were present. Complete and independently
review it; existence is not approval. The six proposed fixture groups are in the design.

Crucial additional gate: prevent the quarantined stage5 ten from being analyzed
through their raw entries in mixed `v6-2`. A downstream report rejection alone
is too late. Design a qualified-source exclusion at the cache-only input boundary;
keep all48 requested slots and mark unavailable explicitly. That gate is unbuilt.

Orientation CTRL needs a new candidate freeze, followed by the existing separate
blind comparison against the historical baseline. Existing production CTRL results
do not cover it. Preserve any disagreement as an additive review candidate; do not
reopen all truth/queue work or automatically adjudicate it.

## 10. Seal, host rules and final closure debt

Do not enumerate, count, hash, stat, resolve or open the unseen batch or
`Bank Statements/new`. The reserved batch is outside the repository under
`C:\Users\GustavoPrietodePaula\CapitalInfusionHoldout\bankStatementAnalysis\batch_20260915`.
This path is a prohibition marker, not a task input. GENESIS remains
`df908f47e3203d09edfcbed3bbe9f1291e19cc267e74ef7259adc4dab890e620`.
Only the later frozen-design evaluation process may unseal it under the plan.

One heavy window at a time, OCR concurrency1, 1.5 GiB free-memory floor and
4 GiB job cap. Lock: `discovery_reports/train13-logs/HARNESS.lock`; acquire
non-queueing and release only the owned holder. Read actual child/controller,
resource, retention/cleanup and release records before a successor. Do not guess
that an absent stream or passed tests imply a successful envelope.

Keep original caches/readings/receipts immutable. No customer contents, financial
values, identifiers beside verdicts, endpoint credentials or raw logs in ordinary
output/Git. Use finite technical projections. No validator-driven extraction,
source arbitration or numeric repairs. No bank-specific workaround. Preserve
production pins and all validated payloads.

V final docs/W3, added-line/message/output privacy scans, exact output-role inventory,
independent review and final composed floors remain owed. Reuse existing scanners;
see `PREP/FINAL-COMPARISON-TIMEOUT-AND-SCAN-REUSE-P.md`. Failed outputs remain in
scope with exact custody exclusions; `.private` or `.log` is not a blanket exemption.
Do not edit a card or source currently bound by frozen live descriptors in place.

## 11. Ordered next actions

1. Read the plan amendment/rulings, this handoff, recovery design/review and actual stage5 receipts. Recheck worktrees/process/lock state. Preserve user edits.
2. Read the private replacement-endpoint note. Configure it privately and prove actual pinned readiness with non-sensitive fixtures; preserve old endpoint/session history and unmatched timing limits.
3. Implement, review and prove the exact 38-only continuation, disposition policy, new descriptor and required accounting contract. Freeze actual original-file bindings before dispatch; no ordinary stage5 resume.
4. Run the new segment under the owned envelope. Inspect actual closure. Only a complete reviewed joined disposition permits stage6; any new interruption stays explicit and stops automatic advancement.
5. Finish stage6, adapt/freeze the orientation descriptor and run stages7–12 serially on their unchanged cohorts.
6. Finish successor compiler/reader proofs and actual input compilation; run both offline comparisons and report missing/unqualified observations honestly.
7. Finish qualified-input B alternative analysis/reporting and orientation blind probe. Complete V docs/privacy/independent closure, compose V/B/P and execute required final validation at that exact source.
8. Close Phase2.3 before beginning Phase2.4. Follow §G.2.4–2.7 in sequence, carrying the completed VL report forward and keeping the unseen batch sealed until its prescribed evaluation.

No new approval is needed just to resume already-authorized work. This handoff
does not itself launch a GPU job, publish/merge/push/tag, or assert completion of
the remaining milestones.
